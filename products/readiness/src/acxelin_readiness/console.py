"""The Acxelin QReadiness console: projects (scan a repository, track findings) and endpoints (grade live TLS and SSH servers).

Runs on acxelin-core's console mechanism; this module is only the product's pages, routes and state.
"""
import hashlib
import json
import math
import re
import shutil
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path

from acxelin_core import console as core
from acxelin_core import shell
from acxelin_core.files import write

from . import cbom, compliance, endpoints, evidence, owners, pacing, pipeline, remote, workspace
from .detectors import deps
from .rank import Horizon

MAX_TARGETS = 500
WEIGHT = {"critical": 8, "high": 4, "medium": 2, "low": 1}
IMPORTANCE = {"critical": 4, "high": 3, "medium": 2, "": 2, "low": 1}  # a service with no importance given counts as medium
TOKEN = re.compile(r"[A-Za-z0-9_]{20,255}")
STATUS = {"open": "To do", "planned": "Planned", "in_progress": "In progress", "fixed": "Fixed", "exception": "Accepted risk"}  # as the page shows them


class Readiness:
    def __init__(self, home):
        self.home = Path(home)
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.store = workspace.ProjectStore(self.home / "workspace.json")
        self.history = self.home / "history.json"
        self.remote_dir, self.remote_file, self.token_file = self.home / "github", self.home / "github.json", self.home / "github-token"
        self.import_dir, self.import_file = self.home / "imports", self.home / "imports.json"
        self.folder = None
        self.projects = []
        self.cache = None
        self.job = {"running": False, "stage": "", "error": None, "selected": 0, "last": None, "forgotten": False}
        self.all = {"running": False, "done": 0, "total": 0, "current": "", "failed": []}
        self.github_api = remote.API
        self.ep_history = self.home / "endpoints-history.json"
        self.ep_hosts = self.home / "endpoints-hosts.json"
        self.ep = {"running": False, "error": None, "history": [], **read_hosts(self.ep_hosts)}
        try:
            saved = json.loads(self.ep_history.read_text()) if self.ep_history.exists() else []
            number = lambda v, top: type(v) in (int, float) and math.isfinite(v) and 0 <= v <= top
            self.ep["history"] = [r for r in saved if isinstance(r, dict) and number(r.get("finished"), 2**33) and (r.get("score") is None or number(r.get("score"), 100))][-30:] \
                if isinstance(saved, list) else []
        except (OSError, ValueError):
            pass  # a damaged history starts again; it holds no findings
        self.notice = None
        settings = self.home / "settings.json"
        try:
            if settings.exists():
                self.folder = Path(json.loads(settings.read_text())["directory"])
        except (OSError, ValueError, KeyError, TypeError):
            self.notice = "The console's settings file was damaged, so the repositories folder has to be chosen again."
        try:
            self.store.read()
        except ValueError:  # a damaged workspace: keep it aside for recovery and start an empty one, rather than not starting
            kept = self.store.path.with_name(f"{self.store.path.name}.damaged-{int(time.time())}")
            self.store.path.replace(kept)
            self.notice = f"The project workspace was damaged; it was kept as {kept.name} and the console started with an empty one."
        self.reload()

    def reload(self):
        """The chosen folder's registered repositories, with the most recently scanned one selected."""
        self.projects = []
        for name in self.store.read()["registrations"].get(self.store.key(self.folder), []) if self.folder else []:
            try:
                self.projects.append(self.approved(name))
            except (OSError, ValueError):
                pass  # a stored name never grants access beyond today's chosen folder
        self.projects += [self.remote_dir / name for name in self.remotes()]
        self.projects += [self.import_dir / name for name in self.imports()]
        saved = [(a["finished"], i, a) for i, a in enumerate(self.store.assessment(p) for p in self.projects) if a]
        self.job.update(last=None, selected=0, error=None, stage="")
        if saved:
            _, self.job["selected"], self.job["last"] = max(saved, key=lambda s: s[:2])

    # --- first run and the repository folder

    def status(self, body):
        available = []
        if self.folder:
            try:
                available = sorted(p.name for p in self.folder.iterdir() if not p.name.startswith(".") and p.is_dir() and not p.is_symlink())[:200]
            except OSError:
                pass
        return 200, {"configured": bool(self.folder), "directory": str(self.folder or ""), "available": available, "example": str(Path.home() / "code"),
                     "projects": [{"id": i, "name": self.label(p)} for i, p in enumerate(self.projects)], "selected": self.job["selected"],
                     "github_token": self.token_file.exists(), "notice": self.notice}

    def setup(self, body):
        d = body.get("directory")
        try:
            path = Path(d).expanduser().resolve() if isinstance(d, str) and d.strip() else None
        except (RuntimeError, OSError):
            path = None  # ~someone for an unknown user, or a path the system refuses
        if not path or not path.is_dir():
            raise ValueError("Choose an existing folder: the one that holds the repositories you want to scan")
        with self.lock:
            if self.job["running"]:
                raise ValueError("Wait for the running scan to finish, or stop it, before choosing another folder")
            write(self.home / "settings.json", json.dumps({"directory": str(path)}).encode(), secret=True)
            self.folder = path
            self.reload()
        return 200, {"directory": str(path)}

    def approved(self, name):
        root = self.folder
        if not root or not isinstance(name, str) or not name or len(name) > 255 or Path(name).name != name or name.startswith(".") or "\\" in name:
            raise ValueError("Choose a repository inside the folder you set up")
        path = (root / name).resolve()
        if (root / name).is_symlink() or not path.is_relative_to(root) or not path.is_dir():
            raise ValueError("Choose a repository inside the folder you set up (symlinks and outside paths are refused)")
        return path

    # --- GitHub repositories, downloaded into the console's own folder for each scan

    def remotes(self):
        """The saved GitHub links by folder name; a damaged file starts again rather than stopping the console."""
        try:
            saved = json.loads(self.remote_file.read_text()) if self.remote_file.exists() else {}
            return {k: v for k, v in saved.items() if isinstance(k, str) and isinstance(v, str) and remote.parse(v)}
        except (OSError, ValueError, AttributeError):
            return {}

    def label(self, path):
        if path.parent == self.import_dir:
            return "Imported: " + self.imports().get(path.name, path.name)
        if path.parent == self.remote_dir:
            url = self.remotes().get(path.name)
            return "github.com/" + remote.label(url) if url else path.name
        return path.name

    # --- CBOMs from other tools, kept owner-only in the console's folder

    def imports(self):
        try:
            saved = json.loads(self.import_file.read_text()) if self.import_file.exists() else {}
            return {k: v for k, v in saved.items() if isinstance(k, str) and isinstance(v, str) and re.fullmatch(r"[a-z0-9]{1,40}-[0-9a-f]{8}\.json", k)}
        except (OSError, ValueError, AttributeError):
            return {}

    def import_cbom(self, body):
        name, bom = body.get("name"), body.get("cbom")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("Give the CBOM a name of up to 200 characters, such as its file name")
        if not isinstance(bom, dict) or bom.get("bomFormat") != "CycloneDX" or not isinstance(bom.get("components", []), list):
            raise ValueError("Choose a CycloneDX CBOM: a JSON file with bomFormat CycloneDX and a list of components")
        slug = re.sub(r"[^a-z0-9]+", "", name.lower())[:40] or "cbom"
        file = f"{slug}-{hashlib.sha256(name.strip().encode()).hexdigest()[:8]}.json"
        with self.lock:
            if self.job["running"]:
                raise ValueError("Wait for the running scan to finish, or stop it")
            known = self.imports()
            if file not in known and len(known) >= 200:
                raise ValueError("The console keeps at most 200 imported CBOMs")
            write(self.import_dir / file, json.dumps(bom).encode(), secret=True)
            write(self.import_file, json.dumps(known | {file: name.strip()}).encode(), secret=True)
            path = self.import_dir / file
            if path not in self.projects:
                self.projects.append(path)
            return 200, {"project": self.projects.index(path)}

    def github(self, body):
        url = body.get("url")
        owner, repo, ref = remote.parse(url)
        exact = f"{owner}/{repo}" + (f"@{ref}" if ref else "")  # branches differ by case; Windows folders do not
        name = f"{owner}--{repo}-{hashlib.sha256(exact.encode()).hexdigest()[:8]}"
        with self.lock:
            known = self.remotes()
            if name not in known:
                if len(known) >= 200:
                    raise ValueError("The console keeps at most 200 GitHub repositories")
                write(self.remote_file, json.dumps(known | {name: url.strip()}).encode(), secret=True)
            path = self.remote_dir / name
            if path not in self.projects:
                self.projects.append(path)
            return 200, {"project": self.projects.index(path)}

    def token(self, body):
        value = body.get("token")
        if value == "":
            self.token_file.unlink(missing_ok=True)
            return 200, {"saved": False}
        if not isinstance(value, str) or not TOKEN.fullmatch(value):
            raise ValueError("Paste a GitHub access token: letters, digits and underscores only, such as github_pat_…")
        write(self.token_file, value.encode(), secret=True)
        return 200, {"saved": True}

    # --- projects

    def register(self, body):
        path = self.approved(body.get("name"))
        self.store.register(self.folder, path.name)
        with self.lock:
            if path not in self.projects:
                self.projects.append(path)
            return 200, {"project": self.projects.index(path)}

    def selected(self, body):
        i = body.get("project")
        if type(i) is not int or not 0 <= i < len(self.projects):
            raise ValueError("Choose a registered project")
        p = self.projects[i]
        if p.parent == self.import_dir:
            if p.name not in self.imports():
                raise ValueError("Choose a registered project")
            return i, p
        if p.parent == self.remote_dir:
            if p.name not in self.remotes():
                raise ValueError("Choose a registered project")
            return i, p
        return i, self.approved(p.name)

    def remove(self, body):
        """Take a project off the list, with its saved results and tracking. A repository on this computer is never touched; a GitHub
        download and an imported CBOM, which live in the console's own folder, are deleted."""
        with self.lock:
            if self.job["running"]:
                raise ValueError("Wait for the running scan to finish, or stop it, before removing a project")
        _, path = self.selected(body)
        name = self.label(path)
        self.forget(path)
        return 200, {"removed": name}

    def forget(self, path):
        own = lambda folder: path.parent == folder and not path.is_symlink() and path.resolve().parent == folder.resolve()
        if path.parent == self.remote_dir:
            write(self.remote_file, json.dumps({k: v for k, v in self.remotes().items() if k != path.name}).encode(), secret=True)
            if own(self.remote_dir):
                shutil.rmtree(path, ignore_errors=True)
        elif path.parent == self.import_dir:
            write(self.import_file, json.dumps({k: v for k, v in self.imports().items() if k != path.name}).encode(), secret=True)
            if own(self.import_dir):
                path.unlink(missing_ok=True)
        self.store.forget(path, None if path.parent in (self.remote_dir, self.import_dir) else self.folder)
        with self.lock:
            self.reload()

    def project_status(self, body):
        with self.lock:
            state = dict(self.job) | {"count": len(self.projects)}
        if self.projects and state["last"]:
            try:
                saved = self.store.assessment(self.projects[state["selected"]])
                if saved and saved["finished"] >= state["last"]["finished"]:
                    state["last"] = saved
            except (OSError, ValueError):
                state["workspace_error"] = "The saved workspace is unavailable; this session's results are kept."
        if state["last"]:
            state["last"] = {k: v for k, v in state["last"].items() if k != "relationships"}
        try:
            state["history"] = workspace.read_history(self.history)
        except (OSError, ValueError):
            state["history"] = []
        return 200, state

    def scan(self, body):
        i, path = self.selected(body)
        self.begin(i)

        def work():
            try:
                refused = self.scan_one(path)
                if refused and path.parent == self.remote_dir and self.store.assessment(path) is None:  # a link that never worked is not kept
                    self.forget(path)
                    with self.lock:
                        self.job.update(error=f"{refused} It was not added to your projects.", forgotten=True)
            finally:
                with self.lock:
                    self.job["running"] = False
        threading.Thread(target=work, daemon=True, name="project-scan").start()
        return 200, {"started": i}

    def begin(self, i):
        with self.lock:
            if self.job["running"]:
                raise ValueError("A project scan is already running")
            if self.cache is None:
                from .crawler import ParseCache
                self.cache = ParseCache()
            self.cancel.clear()
            self.job.update(running=True, stage="Preparing project", error=None, selected=i, forgotten=False)

    def scan_one(self, path):
        """Scan or re-read one project and save it; a failure is kept in job["error"], never raised."""
        def progress(stage):
            with self.lock:
                self.job["stage"] = stage
        try:
            name = None
            if path.parent == self.remote_dir:
                progress("Downloading from GitHub")
                url = self.remotes()[path.name]
                remote.fetch(url, path, token=self.token_file.read_text().strip() if self.token_file.exists() else None)
                name = remote.label(url)
            if path.parent == self.import_dir:
                progress("Reading the imported CBOM")
                result = workspace.imported(path, self.imports()[path.name])
            else:
                cfg, note = workspace.repo_settings(path) if path.parent != self.remote_dir else ({}, None)  # a download's own settings are not trusted
                horizon = Horizon(cfg.get("shelf_life", 10), cfg.get("migration", 5), cfg.get("crqc_year", 2035), owners.secrets(self.store.owner_rules(path)))
                result = workspace.scan(path, history=self.history, progress=progress, exclude=[self.store.path], cancel=self.cancel, cache=self.cache, name=name,
                                        horizon=horizon, settings=cfg)
                if note:
                    result["notes"].insert(0, note)
            result["project_key"] = self.store.key(path)
            try:
                result = self.store.save(path, result)
            except (OSError, ValueError):
                result["notes"].append("The workspace could not be saved; this result is kept until the console closes. Check the folder's permissions and size.")
            with self.lock:
                self.job["last"] = result
        except (workspace.ScanStopped, remote.Refused, workspace.SettingsError) as error:
            with self.lock:
                self.job["error"] = str(error)
            return str(error) if isinstance(error, remote.Refused) else None
        except Exception:  # source-sensitive failures are never echoed or logged with their contents
            with self.lock:
                self.job["error"] = "The project scan failed. Check the folder's permissions and the source's syntax, then try again; `acxelin-qreadiness scan` shows details."

    # --- every project at once

    def scan_all(self, body):
        """Add every repository in the chosen folder, then scan all projects one after another."""
        if self.folder:
            for name in self.status({})[1]["available"]:
                try:
                    self.register({"name": name})
                except (OSError, ValueError):
                    pass
        with self.lock:
            targets = list(enumerate(self.projects))
        if not targets:
            raise ValueError("Add a repository first: choose a folder, a GitHub link or an organisation")
        self.begin(targets[0][0])
        self.all = {"running": True, "done": 0, "total": len(targets), "current": "", "failed": []}

        def work():
            try:
                for i, path in targets:
                    if self.cancel.is_set():
                        break
                    with self.lock:
                        self.all["current"], self.job["selected"], self.job["error"] = self.label(path), i, None
                    self.scan_one(path)
                    with self.lock:
                        if self.job["error"]:
                            self.all["failed"].append({"name": self.label(path), "error": self.job["error"]})
                        self.all["done"] += 1
            finally:
                with self.lock:
                    self.job["running"] = self.all["running"] = False
                    self.all["current"] = ""
        threading.Thread(target=work, daemon=True, name="scan-all").start()
        return 200, {"started": len(targets)}

    def github_org(self, body):
        token = self.token_file.read_text().strip() if self.token_file.exists() else None
        links = remote.organisation(body.get("org"), token=token, api=self.github_api)
        known = set(self.remotes().values())
        new = [u for u in links if u not in known]
        room = max(0, 200 - len(known))
        added = [self.github({"url": u})[1]["project"] for u in new[:room]]
        return 200, {"added": len(added), "projects": added, "left_out": len(new) - len(added)}

    def coverage(self, body):
        """What Readiness tracks: kinds of asset, every algorithm with its verdict, and every place it looks."""
        from .coverage import summary
        return 200, summary()

    def overview(self, body):
        """Every project's latest result side by side, findings by business service across them, and the scheduled scans."""
        with self.lock:
            projects, scan_all = list(enumerate(self.projects)), dict(self.all) | {"stage": self.job["stage"] if self.all["running"] else ""}
        saved, rows, services, libraries, actions = self.store.read()["projects"], [], {}, {}, {}
        board = {"weakest": None, "projects": len(projects), "scanned": 0, "critical": 0, "high": 0, "fix_now": 0, "recordable": 0, "deadline_findings": 0,
                 "to_fix": 0, "done": 0, "effort": Counter(), "coverage": [], "pairs": []}
        for i, path in projects:
            record = saved.get(self.store.key(path))
            if not record:
                rows.append({"id": i, "name": self.label(path), "scanned": False})
                continue
            v = workspace.ProjectStore.view(record, graph=False)
            live = [a for a in v["assets"] if not a["test_only"]]
            cmp = v.get("comparison") or {}
            rows.append({"id": i, "name": self.label(path), "scanned": True, "finished": v["finished"], "fix_now": v["summary"]["headline"]["fix_now"],
                         "tiers": dict(Counter(a["tier"] for a in live)), "new": cmp.get("new") if cmp.get("baseline") else None,
                         "gone": cmp.get("not_observed") if cmp.get("baseline") else None})
            for a in live:
                hint = a.get("owner_hint") or {}
                if hint.get("service") and a["tier"] != "ok":
                    s = services.setdefault(hint["service"], {"service": hint["service"], "critical": 0, "high": 0, "medium": 0, "low": 0, "projects": set(), "importance": ""})
                    s[a["tier"]] += 1
                    s["projects"].add(self.label(path))
                    s["importance"] = max(s["importance"], hint.get("importance", ""), key=lambda x: IMPORTANCE[x] if x else 0)
            self.tally(board, actions, v, live, self.label(path))
            for x in v.get("libraries", []):
                lib = libraries.setdefault((x["ecosystem"], x["name"], x.get("version", "")),
                                           {**x, "pq_needed": deps.pq_needed(x["ecosystem"], x["name"]), "projects": set()})
                lib["projects"].add(self.label(path))
        for s in services.values():
            s["risk"] = IMPORTANCE.get(s["importance"], 2) * sum(WEIGHT[k] * s[k] for k in WEIGHT)
        ranked = sorted(({**s, "projects": sorted(s["projects"])} for s in services.values()),
                        key=lambda s: (-s["risk"], -s["critical"], -s["high"], s["service"]))
        libs = sorted(({**x, "projects": sorted(x["projects"])} for x in libraries.values()),
                      key=lambda x: (x["pq"] or not x["pq_needed"], -len(x["projects"]), x["name"]))
        choice = self.store.deadline_choice()
        default = ["us"], ["enterprise"]  # nothing chosen: NIST IR 8547, not NSA's national-security dates
        try:
            chosen = (choice.get("countries"), choice.get("sectors")) if choice.get("countries") or choice.get("sectors") else default
            due = [d for d in compliance.deadlines(chosen[0] or ["us"], chosen[1] or []) if not d["passed"]]
        except (ValueError, TypeError):  # a damaged saved choice: show the default, and the form can save a good one
            choice, due = {"countries": [], "sectors": []}, [d for d in compliance.deadlines(*default) if not d["passed"]]
        return 200, {"projects": rows, "services": ranked, "libraries": libs, "scan_all": scan_all, "watch": watch_runs(self.home),
                     "board": summary(board, actions, ranked, libs) | {"next_deadline": due[0] if due else None, "deadlines": due},
                     "deadline_choice": choice, "countries": compliance.COUNTRIES, "sectors": compliance.SECTORS}

    @staticmethod
    def tally(board, actions, v, live, name):
        """Add one project's latest scan to the board summary."""
        from .catalog import CATALOG, SHOR
        shor = [a for a in live if a["tier"] != "ok" and a["algorithm"] in CATALOG and CATALOG[a["algorithm"]].threat == SHOR]
        board["scanned"] += 1
        board["critical"] += sum(a["tier"] == "critical" for a in live)
        board["high"] += sum(a["tier"] == "high" for a in live)
        board["deadline_findings"] += len(shor)
        board["recordable"] += sum(CATALOG[a["algorithm"]].primitive != "signature" for a in shor)
        for a in live:
            t = a.get("tracking") or {}
            if a["tier"] != "ok" or t.get("status", "open") != "open":
                board["to_fix"] += 1
                board["done"] += t.get("status") == "exception" or t.get("status") == "fixed" and not t.get("still_found")
            if a.get("effort"):
                board["effort"][a["effort"]["level"]] += 1
        s = v["summary"]
        now = s["headline"]["fix_now"]
        board["fix_now"] += now
        if board["weakest"] is None or now > board["weakest"]["fix_now"]:
            board["weakest"] = {"name": name, "fix_now": now}
        before = [h["summary"]["headline"]["fix_now"] for h in v.get("history", []) if h.get("finished", 0) < v["finished"] and "headline" in h["summary"]]
        if before:
            board["pairs"].append((now, before[-1]))  # the trend compares the same projects, then and now
        board["coverage"].append(s.get("coverage"))
        for rank, x in enumerate(a for a in (v.get("outlook") or {}).get("actions", []) if a.get("targets")):  # not "nothing to change"
            act = actions.setdefault(x["text"], {"text": x["text"], "rank": rank, "projects": set(), "names": set()})
            act["names"].update(x.get("targets", []))
            act["rank"] = min(act["rank"], rank)
            act["projects"].add(name)

    def select(self, body):
        i, path = self.selected(body)
        with self.lock:
            if self.job["running"]:
                raise ValueError("Wait for the running scan to finish, or stop it")
            self.job.update(last=self.store.assessment(path), selected=i, error=None, stage="")
        return 200, {"selected": i}

    def stop(self, body):
        with self.lock:
            if not self.job["running"]:
                raise ValueError("No project scan is running")
            self.cancel.set()
            self.job["stage"] = "Stopping at the next checkpoint"
        return 200, {"requested": True}

    def track(self, body):
        i, path = self.selected(body)
        with self.lock:
            result = self.store.track(path, body)
            if self.job["last"] and self.job["last"].get("project_key") == self.store.key(path):
                self.job["last"] = result
        return 200, {"saved": True}

    def deadlines(self, body):
        countries, sectors = body.get("countries"), body.get("sectors")
        if not (isinstance(countries, list) and isinstance(sectors, list) and all(isinstance(x, str) for x in countries + sectors)):
            raise ValueError("Choose countries and sectors from the lists")
        compliance.deadlines(countries, sectors)  # refuses an unknown name
        self.store.set_deadline_choice(sorted(set(countries)), sorted(set(sectors)))
        return 200, {"saved": True}

    def owners(self, body):
        i, path = self.selected(body)
        text = body.get("csv")
        rules = [] if text == "" else owners.from_csv(text)
        with self.lock:
            n = self.store.set_owners(path, rules)
            if self.job["last"] and self.job["last"].get("project_key") == self.store.key(path):
                self.job["last"] = self.store.assessment(path)
        return 200, {"rules": n}

    def project_csv(self, body):
        i, path = self.selected(body)
        last = self.store.assessment(path)
        if not last:
            raise ValueError("Scan this repository first")
        rows = [[a["name"], a["algorithm"], a["tier"], a["action"] or a["why"], "; ".join(f"{f}:{n}" for f, n in a["locations"][:50]),
                 ", ".join(a.get("seen", [])), a.get("confidence_level") or "", ", ".join(a.get("missing", [])),
                 a["tracking"]["owner"] or (f"{a['owner_hint']['owner']} ({a['owner_hint']['source']})" if a.get("owner_hint") else ""),
                 (a.get("owner_hint") or {}).get("service", ""), STATUS.get(a["tracking"]["status"], a["tracking"]["status"]), a["tracking"]["due"]]
                for a in last["assets"] if not a["test_only"]]
        return 200, {"csv": evidence.csv_text(["Asset", "Algorithm", "Priority", "What to do", "Places", "Seen as", "Confidence", "Not seen",
                                               "Owner", "Service", "Status", "Due"], rows)}

    # --- endpoints

    @staticmethod
    def targets(body):
        raw = body.get("targets", "")
        if not isinstance(raw, (str, list)):
            raise ValueError("Targets must be text with one per line")
        items = raw if isinstance(raw, list) else re.split(r"[\n,]", raw)
        found = [str(t).strip() for t in items if str(t).strip()]
        if not found:
            raise ValueError("Enter at least one host, such as api.example.com:443")
        if len(found) > MAX_TARGETS:
            raise ValueError(f"At most {MAX_TARGETS} endpoints per scan")
        for t in found:
            endpoints.endpoint(t)
        return found

    def endpoint_status(self, body):
        with self.lock:
            return 200, {"running": self.ep["running"], "error": self.ep["error"], "history": list(self.ep["history"]), "last": self.endpoint_view(),
                         "hosts": {t: list(h["history"]) for t, h in self.ep["hosts"].items()}}

    def endpoint_view(self):
        """Every host's latest result, the last check's hosts first, with what changed for each against its own previous result."""
        hosts, checked = self.ep["hosts"], self.ep["checked"] or {}
        if not hosts:
            return None
        recent = [t for t in dict.fromkeys(checked.get("hosts", [])) if t in hosts]
        order = recent + sorted((t for t in hosts if t not in recent), key=lambda t: -hosts[t]["history"][-1]["finished"])
        rows = [hosts[t]["result"] | {"checked": hosts[t]["history"][-1]["finished"], "verification": endpoints.unverified(hosts[t]["result"])} for t in order]
        grades = lambda t: [h["grade"] for h in hosts[t]["history"][-2:]]
        changes = [{"target": t, "before": grades(t)[0], "after": grades(t)[1]} for t in recent if len(grades(t)) == 2 and len(set(grades(t))) == 2]
        return {"finished": checked.get("finished") or rows[0]["checked"], "targets": checked.get("targets", []), "summary": endpoints.summary(rows),
                "endpoints": rows, "changes": changes, "outlook": endpoints.outlook(rows)}

    def save_hosts(self):
        try:
            write(self.ep_hosts, json.dumps({"hosts": self.ep["hosts"], "last": self.ep["checked"]}).encode(), secret=True)
        except OSError:
            pass  # this session still shows them

    def endpoint_forget(self, body):
        target = body.get("target")
        with self.lock:
            if self.ep["running"]:
                raise ValueError("Wait for the running check to finish")
            if not isinstance(target, str) or target not in self.ep["hosts"]:
                raise ValueError("Choose a host from the list")
            del self.ep["hosts"][target]
            self.save_hosts()
        return 200, {"forgotten": target}

    @staticmethod
    def pacing_of(body):
        """Pacing asked for in the request; nothing when it asks for none, so the gentle default applies."""
        if "aggressive" in body and not isinstance(body["aggressive"], bool):
            raise ValueError("aggressive is true or false")
        return pacing.profile(body.get("rate"), body.get("workers"), body.get("aggressive", False))

    def endpoint_scan(self, body):
        targets = self.targets(body)
        asked = {k: body[k] for k in ("rate", "workers", "aggressive") if k in body}
        options = {"profile": self.pacing_of(asked)} if asked else {}
        with self.lock:
            if self.ep["running"]:
                raise ValueError("An endpoint scan is already running")
            self.ep.update(running=True, error=None)

        def work():
            try:
                results = endpoints.scan(targets, **options)
                now = time.time()
                with self.lock:
                    hosts = self.ep["hosts"]
                    for r in results:
                        h = hosts.pop(r["target"], {"history": []})  # re-inserted last: the dict keeps the most recently checked at the end
                        hosts[r["target"]] = {"result": r, "history": (h["history"] + [{"finished": now, "grade": r["grade"]}])[-30:]}
                    for t in list(hosts)[:-MAX_TARGETS]:
                        del hosts[t]  # at most MAX_TARGETS hosts; the longest unchecked go first
                    self.ep["checked"] = {"targets": targets, "hosts": [r["target"] for r in results], "finished": now}
                    self.save_hosts()
                    s = self.endpoint_view()["summary"]
                    self.ep["history"] = self.ep["history"][-29:] + [{"finished": now, "score": s["score"], "coverage": s["coverage"], "endpoints": s["endpoints"]}]
                    try:
                        write(self.ep_history, json.dumps(self.ep["history"]).encode(), secret=True)
                    except OSError:
                        pass  # this session still shows the trend
            except Exception:
                with self.lock:
                    self.ep["error"] = "The endpoint scan failed. Check the host names and your network, then try again."
            finally:
                with self.lock:
                    self.ep["running"] = False
        threading.Thread(target=work, daemon=True, name="endpoint-scan").start()
        return 200, {"started": len(targets)}

    def endpoint_csv(self, body):
        with self.lock:
            last = self.endpoint_view()
        if not last:
            raise ValueError("Check endpoints first")
        c = lambda r, k: (r.get("certificate") or {}).get(k, "")
        return 200, {"csv": evidence.csv_text(["Endpoint", "Grade", "Negotiated", "Certificate key", "Expires", "Issuer"],
                                              [[r["target"], r["grade"], r.get("negotiated") or r.get("error") or "", c(r, "key"), c(r, "expires"), c(r, "issuer")]
                                               for r in last["endpoints"]])}

    def endpoint_cbom(self, body):
        targets = self.targets(body)
        with tempfile.TemporaryDirectory(prefix="readiness-endpoints-") as empty:
            r = pipeline.run(Path(empty), "endpoints", tls_targets=[t for t in targets if not t.startswith("ssh://")],
                             ssh_targets=[t.removeprefix("ssh://") for t in targets if t.startswith("ssh://")])
        return 200, {"cbom": cbom.build("endpoints", r.assets, r.artifacts, r.libraries, r.endpoints)}


def summary(board, actions, services, libraries):
    """One page for a board: the level and its trend, what is at risk, what to do first, and whether it rests on enough evidence."""
    known = [c for c in board.pop("coverage") if c is not None]
    gaps = [f"{board['scanned']} of {board['projects']} projects scanned"] if board["scanned"] < board["projects"] else []
    if known and min(known) < 80:
        gaps.append(f"coverage under 80% in {sum(c < 80 for c in known)} of them")
    top = sorted(actions.values(), key=lambda a: (a["rank"], -len(a["projects"]), a["text"]))[:5]
    pairs = board.pop("pairs")
    previous = sum(b for _, b in pairs) if pairs else None
    return {**board, "previous": previous, "change": sum(n for n, _ in pairs) - previous if pairs else None,
            "coverage": min(known) if known else None, "provisional": "; ".join(gaps), "effort": dict(board["effort"]),
            "agility": {"without_code": sum(n for k, n in board["effort"].items() if k in ("setting", "reissue", "upgrade")), "total": sum(board["effort"].values())},
            "actions": [{"text": a["text"], "names": sorted(a["names"])[:4], "projects": sorted(a["projects"])} for a in top],
            "services": [s["service"] for s in services[:3]], "libraries_without_pq": sum(x["pq_needed"] and not x["pq"] for x in libraries)}


def read_hosts(path):
    """Each endpoint's latest result and its dated grades, and which hosts the last check asked about. Anything damaged starts again:
    the file holds no findings, only what the next check finds anew."""
    number = lambda v: type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 2**33

    def sound(t, h):
        try:
            ok = (isinstance(h, dict) and isinstance(h.get("result"), dict) and h["result"].get("target") == t and h["result"].get("grade") in endpoints.GRADES
                  and isinstance(h.get("history"), list) and 0 < len(h["history"]) <= 30
                  and all(isinstance(x, dict) and number(x.get("finished")) and x.get("grade") in endpoints.GRADES for x in h["history"]))
            return ok and bool(endpoints.outlook([h["result"]]) | endpoints.summary([h["result"]]))  # the views it feeds can read it
        except (KeyError, TypeError, ValueError, AttributeError):
            return False
    try:
        saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        hosts = {t: h for t, h in list(saved.get("hosts", {}).items())[-MAX_TARGETS:] if isinstance(t, str) and sound(t, h)}
        last = saved.get("last")
        last = last if isinstance(last, dict) and number(last.get("finished")) and all(
            isinstance(last.get(k), list) and all(isinstance(x, str) for x in last[k]) for k in ("targets", "hosts")) else None
        return {"hosts": hosts, "checked": last}
    except (OSError, ValueError, AttributeError):
        return {"hosts": {}, "checked": None}


def watch_runs(home):
    """The scheduled scans `acxelin-qreadiness watch` recorded for this console, newest first."""
    try:
        runs = json.loads((Path(home) / "watch.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in runs if isinstance(r, dict)][::-1][:50] if isinstance(runs, list) else []


def page():
    return shell.render((Path(__file__).parent / "console.html").read_text(encoding="utf-8"))


def build(home):
    r = Readiness(home)
    routes = {("GET", "/api/status"): r.status, ("POST", "/api/setup"): r.setup,
              ("POST", "/api/projects/register"): r.register, ("POST", "/api/projects/github"): r.github, ("POST", "/api/projects/import"): r.import_cbom, ("POST", "/api/projects/owners"): r.owners, ("POST", "/api/settings/deadlines"): r.deadlines, ("POST", "/api/github/token"): r.token, ("GET", "/api/projects/status"): r.project_status,
              ("POST", "/api/projects/select"): r.select, ("POST", "/api/projects/remove"): r.remove, ("POST", "/api/projects/scan"): r.scan, ("POST", "/api/projects/cancel"): r.stop, ("POST", "/api/projects/track"): r.track,
              ("GET", "/api/endpoints/status"): r.endpoint_status, ("POST", "/api/endpoints/scan"): r.endpoint_scan, ("POST", "/api/endpoints/forget"): r.endpoint_forget,
              ("POST", "/api/endpoints/cbom"): r.endpoint_cbom, ("POST", "/api/projects/csv"): r.project_csv,
              ("POST", "/api/projects/scan-all"): r.scan_all, ("POST", "/api/projects/github-org"): r.github_org, ("GET", "/api/overview"): r.overview, ("GET", "/api/coverage"): r.coverage, ("POST", "/api/endpoints/csv"): r.endpoint_csv}
    return core.App(page(), routes, limits={("POST", "/api/projects/import"): 16_000_000, ("POST", "/api/projects/owners"): 2_000_000})  # a CBOM can be large; read only after sign-in


def run(home, port=8900, open_browser=True, host="127.0.0.1"):
    """Start the console and sign this browser in: the launch address carries a single-use ticket in its fragment."""
    app = build(home)
    server = core.start(app, home, port, host)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/#{app.sessions.ticket()}"
    if open_browser and core.open_in_browser(url, home):
        print(f"Acxelin QReadiness console is open in your browser (http://127.0.0.1:{port}). Press Ctrl+C to stop.")
    else:
        core.link_running(port, home)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()
    return 0



