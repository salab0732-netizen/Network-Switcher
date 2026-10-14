# -*- coding: utf-8 -*-
"""
Network Switcher v8.0 — DTW ELBAYADH / STT / DEV2026

تبديل سلس بين الإنترنت والشبكة الداخلية **بدون تعطيل أي محوّل**.

الفكرة: كلا المحوّلين يبقيان متصلين دائماً. البرنامج يغيّر فقط "أولوية" المسار
(Interface Metric) بحيث يمر الاتصال عبر الشبكة المختارة. لا قطع، لا إعادة اتصال
بالوايفي، لا انتظار DHCP.

الأوضاع:
  • الإنترنت          — كل الحركة عبر محوّل الإنترنت
  • الشبكة الداخلية   — كل الحركة عبر محوّل الشبكة الداخلية
  • الوضع المزدوج     — الإنترنت افتراضياً + عناوين الشبكة الداخلية عبر محوّلها
                        (مسارات مؤقتة تُحذف تلقائياً عند إعادة التشغيل)

لا نوافذ منبثقة: كل الإشعارات داخل الواجهة، وكل أوامر PowerShell تعمل مخفية.
"""
import os
import sys
import json
import re
import time
import queue
import random
import logging
import platform
import threading
import subprocess
import base64
import pathlib
import datetime

import customtkinter as ctk

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:  # Pillow غير مثبّتة: الواجهة تعمل بدون أيقونات مرسومة
    Image = ImageDraw = None
    HAS_PIL = False

APP_NAME = "Network Switcher"
VERSION = "8.2"
BRAND = "DTW ELBAYADH  •  STT  •  DEV2026"
IS_WIN = platform.system() == "Windows"
DEMO = (not IS_WIN) or ("--demo" in sys.argv)

# ── مسارات (AppData بدل مجلد البرنامج — قد يكون Program Files للقراءة فقط) ──
if IS_WIN:
    DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "NetworkSwitcher")
else:
    DATA_DIR = os.path.join(os.path.expanduser("~"), ".network_switcher")
os.makedirs(DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LOG_FILE = os.path.join(DATA_DIR, "network_switcher.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger("NetSwitch")


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# ══════════════════════════════════════════════════════════════════════════════
#  الألوان والخطوط
# ══════════════════════════════════════════════════════════════════════════════
C = {
    "bg": "#0B1120", "side": "#0E1628", "card": "#131C2E", "card2": "#18233A",
    "border": "#22304A", "hover": "#1C2942",
    "text": "#E6EBF5", "muted": "#8A97B1", "faint": "#55627C",
    "inet": "#38BDF8", "intra": "#22C55E", "hybrid": "#A78BFA",
    "ok": "#22C55E", "warn": "#F59E0B", "err": "#EF4444", "gold": "#F5B83D",
}
MODE_META = {
    "internet": {"icon": "🌍", "title": "الإنترنت", "sub": "Internet / WAN",
                 "desc": "كل الحركة عبر الإنترنت", "color": C["inet"]},
    "intranet": {"icon": "🏢", "title": "الشبكة الداخلية", "sub": "Intranet / LAN",
                 "desc": "كل الحركة عبر الشبكة الداخلية", "color": C["intra"]},
    "hybrid":   {"icon": "⇄", "title": "الوضع المزدوج", "sub": "Split routing",
                 "desc": "الإنترنت والداخلية معاً", "color": C["hybrid"]},
}
FONT_FAMILY = "Segoe UI" if IS_WIN else "DejaVu Sans"


def F(size=12, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def draw_icon(kind, color, size=44):
    """أيقونات مرسومة (لا تعتمد على خطوط الإيموجي). تُرجع None إن لم تتوفر Pillow."""
    if not HAS_PIL:
        return None
    S = 256
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = 14
    if kind == "internet":
        d.ellipse((24, 24, 232, 232), outline=color, width=w)
        d.ellipse((84, 24, 172, 232), outline=color, width=w)
        d.line((24, 128, 232, 128), fill=color, width=w)
        d.line((128, 24, 128, 232), fill=color, width=w)
        d.arc((40, -40, 216, 110), 30, 150, fill=color, width=w)
        d.arc((40, 146, 216, 296), 210, 330, fill=color, width=w)
    elif kind == "intranet":
        d.rounded_rectangle((52, 28, 204, 232), radius=14, outline=color, width=w)
        for r in range(3):
            for c in range(3):
                x, y = 78 + c * 38, 56 + r * 40
                d.rectangle((x, y, x + 22, y + 22), fill=color)
        d.rectangle((108, 182, 148, 232), fill=color)
        d.line((20, 232, 236, 232), fill=color, width=w)
    else:  # hybrid
        d.line((40, 86, 200, 86), fill=color, width=w + 4)
        d.polygon([(232, 86), (186, 50), (186, 122)], fill=color)
        d.line((56, 170, 216, 170), fill=color, width=w + 4)
        d.polygon([(24, 170), (70, 134), (70, 206)], fill=color)
    im = im.resize((size * 2, size * 2), Image.LANCZOS)
    return ctk.CTkImage(light_image=im, dark_image=im, size=(size, size))


# ══════════════════════════════════════════════════════════════════════════════
#  PowerShell مخفي تماماً (لا تومض أي نافذة سوداء)
# ══════════════════════════════════════════════════════════════════════════════
_NO_WINDOW = 0x08000000 if IS_WIN else 0


def _startupinfo():
    if not IS_WIN:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return si


def run_hidden(args, timeout=20):
    return subprocess.run(
        args, capture_output=True, timeout=timeout, encoding="utf-8", errors="replace",
        creationflags=_NO_WINDOW, startupinfo=_startupinfo(), stdin=subprocess.DEVNULL)


_PS_PREFIX = ("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
              "$ProgressPreference='SilentlyContinue';")


def ps_json(script, timeout=25):
    """تشغيل سكربت PowerShell يُرجع JSON في آخر سطر."""
    enc = base64.b64encode((_PS_PREFIX + script).encode("utf-16-le")).decode("ascii")
    try:
        # EncodedCommand: لا مشاكل اقتباس مع علامات " أو ' أو أسطر متعددة
        r = run_hidden(["powershell.exe", "-NoProfile", "-NonInteractive", "-NoLogo",
                        "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                       timeout=timeout)
    except subprocess.TimeoutExpired:
        log.warning("PowerShell timeout")
        return None
    except Exception as e:
        log.error(f"PowerShell error: {e}")
        return None
    if r.stderr.strip():
        log.debug(f"ps stderr: {r.stderr.strip()[:500]}")
    for line in reversed(r.stdout.strip().splitlines()):
        line = line.strip().lstrip("\ufeff")
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                break
    log.warning(f"ps no json: {r.stdout[-300:]!r} {r.stderr[-300:]!r}")
    return None


def ps_str(s):
    """نص آمن داخل '...' في PowerShell"""
    return "'" + str(s).replace("'", "''") + "'"


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


_OCT = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_IP_RE = re.compile(rf"^{_OCT}(?:\.{_OCT}){{3}}$")
_CIDR_RE = re.compile(rf"^{_OCT}(?:\.{_OCT}){{3}}/(?:3[0-2]|[12]?\d)$")


# ══════════════════════════════════════════════════════════════════════════════
#  طبقة الشبكة (Windows)
# ══════════════════════════════════════════════════════════════════════════════
SNAPSHOT_PS = r"""
$ErrorActionPreference='SilentlyContinue'
$out=@()
$ads = Get-NetAdapter | Where-Object { $_.Status -ne 'Not Present' -and
  $_.InterfaceDescription -notmatch 'Loopback|Tunnel|Teredo|Bluetooth|ISATAP|6to4|WAN Miniport|Hyper-V|VirtualBox|VMware|TAP-|Npcap|Wi-Fi Direct|Kernel Debug' }
foreach($a in $ads){
  $ip  = Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1
  $rt  = Get-NetRoute -InterfaceIndex $a.ifIndex -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1
  $ipi = Get-NetIPInterface -InterfaceIndex $a.ifIndex -AddressFamily IPv4
  $dns = @((Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4).ServerAddresses | Where-Object { $_ })
  $out += [pscustomobject]@{ name="$($a.Name)"; index=[int]$a.ifIndex; desc="$($a.InterfaceDescription)";
    status="$($a.Status)"; media="$($a.PhysicalMediaType)"; ip="$($ip.IPAddress)"; prefix=[int]$ip.PrefixLength;
    gw="$($rt.NextHop)"; metric=[int]$ipi.InterfaceMetric; auto="$($ipi.AutomaticMetric)"; dns=$dns }
}
$best = (Find-NetRoute -RemoteIPAddress 8.8.8.8 | Where-Object { $_.InterfaceIndex } | Select-Object -First 1).InterfaceIndex
$p = New-Object System.Net.NetworkInformation.Ping
function P($h){ if(-not $h){ return -1 }; try { $r=$p.Send($h,1000); if($r.Status -eq 'Success'){ [int]$r.RoundtripTime } else { -1 } } catch { -1 } }
[pscustomobject]@{ adapters=@($out); best=[int]$best; inet_ms=(P '8.8.8.8'); intra_ms=(P __INTRA__) } | ConvertTo-Json -Compress -Depth 5
"""

DETECT_PS = r"""
$ErrorActionPreference='SilentlyContinue'
$res=@()
foreach($i in __IPS__){
  & ping.exe -n 1 -w 1200 -S $i 8.8.8.8 | Out-Null
  $res += [pscustomobject]@{ ip=$i; ok=($LASTEXITCODE -eq 0) }
}
[pscustomobject]@{ r=@($res) } | ConvertTo-Json -Compress -Depth 4
"""

APPLY_PS = r"""
$ErrorActionPreference='SilentlyContinue'
$c = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('__CFG__')) | ConvertFrom-Json
# 0) إعادة تفعيل المحوّلات المطلوبة إن كانت معطّلة (الإصدار السابق كان يعطّلها)
foreach($i in @($c.enable)){ if($i -gt 0){
  Get-NetAdapter -InterfaceIndex $i | Enable-NetAdapter -Confirm:$false
  for($t=0; $t -lt 24; $t++){
    $ok = Get-NetIPAddress -InterfaceIndex $i -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' }
    if($ok){ break }; Start-Sleep -Milliseconds 500 }
} }
function SetM($i,$m){ if($i -gt 0){ foreach($af in 'IPv4','IPv6'){ Set-NetIPInterface -InterfaceIndex $i -AddressFamily $af -InterfaceMetric $m } } }
# 1) تنظيف ما أضافه البرنامج سابقاً فقط
foreach($r in @($c.remove)){ if($r){ Remove-NetRoute -DestinationPrefix $r.prefix -InterfaceIndex $r.ifIndex -NextHop $r.nexthop -PolicyStore ActiveStore -Confirm:$false } }
Get-DnsClientNrptRule | Where-Object { $_.Comment -eq 'NetSwitch' } | ForEach-Object { Remove-DnsClientNrptRule -Name $_.Name -Force }
$added=@(); $errs=@()
# 2) الأولويات — لا تعطيل لأي محوّل
switch($c.mode){
  'reset'    { foreach($i in @($c.inet,$c.intra)){ if($i -gt 0){ foreach($af in 'IPv4','IPv6'){ Set-NetIPInterface -InterfaceIndex $i -AddressFamily $af -AutomaticMetric Enabled } } } }
  'intranet' { SetM $c.intra 5; SetM $c.inet 500 }
  default    { SetM $c.inet 5;  SetM $c.intra 500 }
}
# 3) الوضع المزدوج: مسارات مؤقتة (ActiveStore) للشبكة الداخلية
if($c.mode -eq 'hybrid'){
  foreach($p in @($c.subnets)){
    try { New-NetRoute -DestinationPrefix $p -InterfaceIndex $c.intra -NextHop $c.intra_gw -RouteMetric 1 -PolicyStore ActiveStore -ErrorAction Stop | Out-Null
          $added += [pscustomobject]@{ prefix=$p; ifIndex=[int]$c.intra; nexthop=$c.intra_gw } }
    catch { $errs += "$p : $($_.Exception.Message)" }
  }
  if($c.domain -and @($c.dns).Count -gt 0){
    try { Add-DnsClientNrptRule -Namespace $c.domain -NameServers @($c.dns) -Comment 'NetSwitch' -ErrorAction Stop }
    catch { $errs += "DNS: $($_.Exception.Message)" }
  }
}
# 4) شبكة داخلية بلا بوابة افتراضية: مسار افتراضي مؤقت عبر البوابة المُدخلة يدوياً
if($c.mode -eq 'intranet' -and $c.gw_route){
  $has = Get-NetRoute -InterfaceIndex $c.intra -DestinationPrefix '0.0.0.0/0'
  if(-not $has){
    try { New-NetRoute -DestinationPrefix '0.0.0.0/0' -InterfaceIndex $c.intra -NextHop $c.gw_route -RouteMetric 0 -PolicyStore ActiveStore -ErrorAction Stop | Out-Null
          $added += [pscustomobject]@{ prefix='0.0.0.0/0'; ifIndex=[int]$c.intra; nexthop=$c.gw_route } }
    catch { $errs += "GW: $($_.Exception.Message)" }
  }
}
Clear-DnsClientCache
Start-Sleep -Milliseconds 300
$ist = "$((Get-NetAdapter -InterfaceIndex $c.intra).Status)"
$best = (Find-NetRoute -RemoteIPAddress 8.8.8.8 | Where-Object { $_.InterfaceIndex } | Select-Object -First 1).InterfaceIndex
[pscustomobject]@{ best=[int]$best; added=@($added); errors=@($errs); intra_status=$ist } | ConvertTo-Json -Compress -Depth 5
"""


ENABLE_PS = r"""
$ErrorActionPreference='SilentlyContinue'
foreach($i in __IDX__){
  Get-NetAdapter -InterfaceIndex $i | Enable-NetAdapter -Confirm:$false
  for($t=0; $t -lt 20; $t++){
    if(Get-NetIPAddress -InterfaceIndex $i -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '169.254.*' }){ break }
    Start-Sleep -Milliseconds 500 }
}
[pscustomobject]@{ ok=$true } | ConvertTo-Json -Compress
"""

DIAG_PS = r"""
$ErrorActionPreference='SilentlyContinue'
$t  = "=== Get-NetAdapter ===`n" + (Get-NetAdapter | Format-Table Name,InterfaceDescription,Status,ifIndex,MediaConnectionState -AutoSize | Out-String -Width 220)
$t += "=== IP configuration ===`n" + (Get-NetIPConfiguration -All | Format-List InterfaceAlias,InterfaceIndex,IPv4Address,IPv4DefaultGateway,DNSServer | Out-String -Width 220)
$t += "=== Interface metrics ===`n" + (Get-NetIPInterface -AddressFamily IPv4 | Format-Table ifIndex,InterfaceAlias,InterfaceMetric,AutomaticMetric,ConnectionState -AutoSize | Out-String -Width 220)
$t += "=== Default routes ===`n" + (Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Format-Table ifIndex,InterfaceAlias,NextHop,RouteMetric,PolicyStore -AutoSize | Out-String -Width 220)
[pscustomobject]@{ t=$t } | ConvertTo-Json -Compress
"""


class WinBackend:
    def snapshot(self, intra_ping=""):
        host = ps_str(intra_ping) if _IP_RE.match(intra_ping or "") else "''"
        d = ps_json(SNAPSHOT_PS.replace("__INTRA__", host), timeout=25)
        if not d:
            return None
        d["adapters"] = as_list(d.get("adapters"))
        for a in d["adapters"]:
            a["dns"] = [x for x in as_list(a.get("dns")) if x]
            a["is_wifi"] = is_wifi(a)
            a["up"] = (a.get("status", "").lower() == "up")
        return d

    def internet_by_source(self, ips):
        if not ips:
            return {}
        arr = "@(" + ",".join(ps_str(i) for i in ips) + ")"
        d = ps_json(DETECT_PS.replace("__IPS__", arr), timeout=10 + 3 * len(ips))
        if not d:
            return {}
        return {x.get("ip"): bool(x.get("ok")) for x in as_list(d.get("r"))}

    def enable(self, indexes):
        if indexes:
            ps_json(ENABLE_PS.replace("__IDX__", "@(" + ",".join(str(int(i)) for i in indexes) + ")"), timeout=30)

    def diagnostics(self):
        d = ps_json(DIAG_PS, timeout=30)
        return (d or {}).get("t", "تعذّر جمع التقرير")

    def apply(self, cfg):
        payload = base64.b64encode(json.dumps(cfg, ensure_ascii=True).encode("utf-8")).decode("ascii")
        d = ps_json(APPLY_PS.replace("__CFG__", payload), timeout=40)
        if not d:
            return {"best": 0, "added": [], "errors": ["تعذّر تشغيل PowerShell"]}
        d["added"] = as_list(d.get("added"))
        d["errors"] = [e for e in as_list(d.get("errors")) if e]
        return d

    # ── التشغيل مع ويندوز (مهمة مجدولة بصلاحيات عالية = بدون نافذة UAC) ──
    TASK = "DTW Network Switcher"

    def autostart_enabled(self):
        try:
            return run_hidden(["schtasks", "/Query", "/TN", self.TASK], 10).returncode == 0
        except Exception:
            return False

    def set_autostart(self, on):
        try:
            if on:
                if getattr(sys, "frozen", False):
                    tr = f'"{sys.executable}" --minimized'
                else:
                    tr = f'"{pythonw_path()}" "{os.path.abspath(__file__)}" --minimized'
                r = run_hidden(["schtasks", "/Create", "/TN", self.TASK, "/TR", tr,
                                "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"], 15)
            else:
                r = run_hidden(["schtasks", "/Delete", "/TN", self.TASK, "/F"], 15)
            return r.returncode == 0
        except Exception as e:
            log.error(f"autostart: {e}")
            return False


def is_wifi(a):
    s = f"{a.get('name','')} {a.get('desc','')} {a.get('media','')}".lower()
    return any(k in s for k in ("wi-fi", "wifi", "wireless", "wlan", "802.11", "sans fil"))


class DemoBackend:
    """واجهة تجريبية خارج Windows (للمعاينة فقط)"""
    def __init__(self):
        self.best = 12
        self.added = []
        self.eth_disabled = True   # يحاكي محوّلاً عطّله الإصدار السابق

    def snapshot(self, intra_ping=""):
        time.sleep(0.3)
        ads = [
            {"name": "Wi-Fi", "index": 12, "desc": "Intel(R) Wi-Fi 6 AX201", "status": "Up",
             "media": "Native 802.11", "ip": "192.168.1.34", "prefix": 24, "gw": "192.168.1.1",
             "metric": 5 if self.best == 12 else 500, "auto": "Disabled", "dns": ["192.168.1.1"]},
            {"name": "Ethernet", "index": 7, "desc": "Realtek PCIe GbE Family Controller",
             "status": "Disabled" if self.eth_disabled else "Up",
             "media": "802.3", "ip": "" if self.eth_disabled else "10.32.4.17", "prefix": 16,
             "gw": "" if self.eth_disabled else "10.32.0.1",
             "metric": 5 if self.best == 7 else 500, "auto": "Disabled", "dns": ["10.32.0.10"]},
        ]
        for a in ads:
            a["is_wifi"] = is_wifi(a)
            a["up"] = a["status"] == "Up"
        return {"adapters": ads, "best": self.best,
                "inet_ms": random.randint(18, 40) if self.best == 12 else -1,
                "intra_ms": random.randint(1, 4)}

    def internet_by_source(self, ips):
        return {i: i.startswith("192.168") for i in ips}

    def apply(self, cfg):
        time.sleep(1.1)
        if cfg["mode"] == "intranet":
            self.best = cfg["intra"]
        else:
            self.best = cfg["inet"] or 12
        added = [{"prefix": p, "ifIndex": cfg["intra"], "nexthop": cfg["intra_gw"]}
                 for p in cfg.get("subnets", [])] if cfg["mode"] == "hybrid" else []
        return {"best": self.best, "added": added, "errors": [], "intra_status": "Up"}

    def enable(self, indexes):
        time.sleep(0.5)
        if 7 in indexes:
            self.eth_disabled = False

    def diagnostics(self):
        return "demo diagnostics"

    def autostart_enabled(self):
        return False

    def set_autostart(self, on):
        return True


def pythonw_path():
    """مسار pythonw.exe المقابل لمفسّر Python الحالي (يعمل مع python3.exe و python3.12.exe…)"""
    p = pathlib.Path(sys.executable)
    stem = p.stem.lower()
    if stem.startswith("python") and not stem.startswith("pythonw"):
        cand = p.with_name("pythonw" + p.stem[6:] + p.suffix)
        if cand.exists():
            return str(cand)
        cand = p.with_name("pythonw" + p.suffix)
        if cand.exists():
            return str(cand)
    return str(p)


def is_admin():
    if not IS_WIN:
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  الإعدادات
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_CFG = {
    "internet_if": "",
    "intranet_if": "",
    "intranet_subnets": "10.0.0.0/8, 172.16.0.0/12",
    "intranet_domain": "",
    "intranet_gw": "",
    "mode": "",
    "added_routes": [],
}


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception as e:
        log.error(f"config load: {e}")
    return cfg


_CFG_LOCK = threading.RLock()


def save_cfg(cfg):
    try:
        with _CFG_LOCK:
            data = json.loads(json.dumps(cfg))  # نسخة عميقة ثابتة
            tmp = CONFIG_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, CONFIG_FILE)
    except Exception as e:
        log.error(f"config save: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  عناصر الواجهة
# ══════════════════════════════════════════════════════════════════════════════
class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", C["card"])
        kw.setdefault("corner_radius", 14)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", C["border"])
        super().__init__(master, **kw)


class Pill(ctk.CTkLabel):
    def __init__(self, master, text="", color=C["muted"], **kw):
        super().__init__(master, text=text, font=F(11, "bold"), text_color=color,
                         fg_color=C["card2"], corner_radius=10, height=24, padx=10, **kw)

    def set(self, text, color):
        self.configure(text=text, text_color=color)


class ModeCard(Card):
    def __init__(self, master, mode, on_click):
        super().__init__(master, fg_color=C["card"])
        self.mode = mode
        self.meta = MODE_META[mode]
        self.on_click = on_click
        self.active = False
        self.enabled = True
        col = self.meta["color"]

        self.grid_columnconfigure(0, weight=1)
        self.badge = ctk.CTkLabel(self, text="", font=F(11, "bold"), text_color=col)
        self.badge.grid(row=0, column=0, sticky="e", padx=14, pady=(8, 0))
        _img = draw_icon(mode, col, 40)
        self.icon = ctk.CTkLabel(self, text="" if _img else self.meta["icon"], image=_img,
                                 font=F(30), text_color=col)
        self.icon.grid(row=1, column=0, pady=(0, 6))
        self.title = ctk.CTkLabel(self, text=self.meta["title"], font=F(16, "bold"), text_color=C["text"])
        self.title.grid(row=2, column=0)
        self.sub = ctk.CTkLabel(self, text=self.meta["sub"], font=F(11), text_color=C["faint"])
        self.sub.grid(row=3, column=0)
        self.desc = ctk.CTkLabel(self, text=self.meta["desc"], font=F(11), text_color=C["muted"])
        self.desc.grid(row=4, column=0, padx=12, pady=(4, 8))
        self.bar = ctk.CTkProgressBar(self, mode="indeterminate", height=3, corner_radius=2,
                                      progress_color=col, fg_color=C["card"])
        self.bar.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.bar.grid_remove()

        for w in (self, self.badge, self.icon, self.title, self.sub, self.desc):
            w.bind("<Button-1>", lambda e: self._click())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))
            w.configure(cursor="hand2")

    def _click(self):
        if self.enabled:
            self.on_click(self.mode)

    def _hover(self, on):
        if self.active:
            return
        self.configure(fg_color=C["hover"] if (on and self.enabled) else C["card"],
                       border_color=self.meta["color"] if (on and self.enabled) else C["border"])

    def set_active(self, on):
        self.active = on
        col = self.meta["color"]
        self.configure(border_width=2 if on else 1,
                       border_color=col if on else C["border"],
                       fg_color=C["card2"] if on else C["card"])
        self.badge.configure(text="● نشط" if on else "")

    def set_busy(self, on):
        if on:
            self.bar.grid()
            self.bar.start()
        else:
            self.bar.stop()
            self.bar.grid_remove()

    def set_enabled(self, on):
        self.enabled = on
        self.title.configure(text_color=C["text"] if on else C["faint"])


class AdapterCard(Card):
    def __init__(self, master, role):
        super().__init__(master)
        self.role = role
        col = C["inet"] if role == "internet" else C["intra"]
        self.grid_columnconfigure(0, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 2))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text=("محوّل الإنترنت" if role == "internet" else "محوّل الشبكة الداخلية"),
                     font=F(12, "bold"), text_color=col).grid(row=0, column=1, sticky="e")
        self.state_pill = Pill(head, "—")
        self.state_pill.grid(row=0, column=0, sticky="w")
        self.name = ctk.CTkLabel(self, text="غير محدد", font=F(15, "bold"), text_color=C["text"], anchor="e")
        self.name.grid(row=1, column=0, sticky="ew", padx=16)
        self.desc = ctk.CTkLabel(self, text="", font=F(11), text_color=C["faint"], anchor="e")
        self.desc.grid(row=2, column=0, sticky="ew", padx=16)
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.grid(row=3, column=0, sticky="ew", padx=16, pady=(8, 12))
        self.vals = {}
        for i, (k, lbl) in enumerate([("ip", "العنوان"), ("gw", "البوابة"), ("metric", "الأولوية")]):
            grid.grid_columnconfigure(2 - i, weight=1)
            f = ctk.CTkFrame(grid, fg_color=C["card2"], corner_radius=10)
            f.grid(row=0, column=2 - i, sticky="ew", padx=4)
            ctk.CTkLabel(f, text=lbl, font=F(10), text_color=C["faint"]).pack(pady=(6, 0))
            v = ctk.CTkLabel(f, text="—", font=ctk.CTkFont(family="Consolas", size=12), text_color=C["text"])
            v.pack(pady=(0, 6))
            self.vals[k] = v

    def update_from(self, a, is_primary):
        if not a:
            self.name.configure(text="غير محدد")
            self.desc.configure(text="اختره من الإعدادات")
            for v in self.vals.values():
                v.configure(text="—")
            self.state_pill.set("—", C["muted"])
            return
        self.name.configure(text=a["name"])
        self.desc.configure(text=a.get("desc", "")[:48])
        self.vals["ip"].configure(text=a.get("ip") or "—")
        self.vals["gw"].configure(text=a.get("gw") or a.get("gw_manual") or "بلا بوابة")
        self.vals["metric"].configure(text=str(a.get("metric", "—")))
        st = (a.get("status") or "").lower()
        if st == "disabled":
            self.state_pill.set("معطّل • سيُفعَّل", C["warn"])
        elif st == "disconnected":
            self.state_pill.set("الكابل غير موصول", C["err"])
        elif not a.get("up"):
            self.state_pill.set(a.get("status") or "غير متصل", C["err"])
        elif is_primary:
            self.state_pill.set("المسار الرئيسي", C["ok"])
        else:
            self.state_pill.set("متصل • احتياطي", C["muted"])


class Toast(ctk.CTkFrame):
    COLORS = {"success": C["ok"], "error": C["err"], "warning": C["warn"], "info": C["inet"]}

    def __init__(self, master):
        super().__init__(master, fg_color=C["card2"], corner_radius=12,
                         border_width=1, border_color=C["border"])
        self.dot = ctk.CTkLabel(self, text="●", font=F(14), text_color=C["ok"])
        self.lbl = ctk.CTkLabel(self, text="", font=F(12), text_color=C["text"])
        self.lbl.pack(side="right", padx=(6, 16), pady=10)
        self.dot.pack(side="right", padx=(14, 0))
        self._job = None

    def show(self, text, level="info", ms=3200):
        self.dot.configure(text_color=self.COLORS.get(level, C["inet"]))
        self.configure(border_color=self.COLORS.get(level, C["border"]))
        self.lbl.configure(text=text)
        self.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        self.lift()
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(ms, self.place_forget)


# ══════════════════════════════════════════════════════════════════════════════
#  التطبيق
# ══════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    POLL_MS = 6000

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.backend = DemoBackend() if DEMO else WinBackend()
        self.cfg = load_cfg()
        self.admin = is_admin()
        self.snap = None
        self.busy = False
        self._ui_q = queue.Queue()
        self._snap_lock = threading.Lock()
        self._first_snap = True
        self._hero_icons = {}

        self.title(f"{APP_NAME} — DTW ELBAYADH")
        self.configure(fg_color=C["bg"])
        w, h = 1040, 720
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
        self.minsize(960, 700)
        try:
            if IS_WIN:
                self.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass

        self._build()
        self.bind_all("<Control-Key-1>", lambda e: self.request_mode("internet"))
        self.bind_all("<Control-Key-2>", lambda e: self.request_mode("intranet"))
        self.bind_all("<Control-Key-3>", lambda e: self.request_mode("hybrid"))
        self.bind_all("<F5>", lambda e: self.refresh_now())
        self.after(50, self._pump)
        self.after(200, self.refresh_now)
        self.after(self.POLL_MS, self._poll)
        if "--minimized" in sys.argv:
            self.after(300, self.iconify)
        self.log_ui(f"{APP_NAME} v{VERSION} — {'وضع تجريبي' if DEMO else 'Windows'}", "title")
        if not self.admin:
            self.log_ui("البرنامج يعمل بدون صلاحيات المدير — التبديل غير متاح.", "error")

    # ── بناء الواجهة ────────────────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # الشريط الجانبي (يمين — اتجاه عربي)
        side = ctk.CTkFrame(self, fg_color=C["side"], corner_radius=0, width=230)
        side.grid(row=0, column=1, sticky="ns")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(5, weight=1)

        logo = ctk.CTkFrame(side, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=20, pady=(26, 22))
        ctk.CTkLabel(logo, text="⬡", font=F(30), text_color=C["inet"]).pack(side="right")
        lt = ctk.CTkFrame(logo, fg_color="transparent")
        lt.pack(side="right", padx=(0, 10))
        ctk.CTkLabel(lt, text="Network Switcher", font=F(16, "bold"), text_color=C["text"]).pack(anchor="e")
        ctk.CTkLabel(lt, text=f"الإصدار {VERSION}", font=F(11), text_color=C["faint"]).pack(anchor="e")

        self.nav = {}
        for i, (key, label) in enumerate([("home", "الرئيسية"), ("settings", "الإعدادات"), ("log", "سجل العمليات")]):
            b = ctk.CTkButton(side, text=label, anchor="e", font=F(13), height=40, corner_radius=10,
                              fg_color="transparent", hover_color=C["hover"], text_color=C["muted"],
                              command=lambda k=key: self.show_page(k))
            b.grid(row=1 + i, column=0, sticky="ew", padx=14, pady=3)
            self.nav[key] = b

        self.admin_pill = Pill(side, "")
        self.admin_pill.grid(row=6, column=0, sticky="e", padx=20, pady=(0, 10))
        if self.admin:
            self.admin_pill.set("● صلاحيات المدير", C["ok"])
        else:
            self.admin_pill.set("● صلاحيات محدودة", C["err"])
        ctk.CTkLabel(side, text="DTW ELBAYADH", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                     text_color=C["gold"]).grid(row=7, column=0, sticky="e", padx=20)
        ctk.CTkLabel(side, text="STT  /  DEV2026", font=ctk.CTkFont(family="Consolas", size=11),
                     text_color=C["faint"]).grid(row=8, column=0, sticky="e", padx=20, pady=(0, 20))

        # منطقة المحتوى
        self.content = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.pages = {
            "home": self._build_home(self.content),
            "settings": self._build_settings(self.content),
            "log": self._build_log(self.content),
        }
        self.toast = Toast(self.content)
        self.show_page("home")

    def _page(self, parent, title, subtitle):
        p = ctk.CTkFrame(parent, fg_color=C["bg"], corner_radius=0)
        p.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(p, text=title, font=F(24, "bold"), text_color=C["text"]).grid(
            row=0, column=0, sticky="e", padx=32, pady=(20, 0))
        ctk.CTkLabel(p, text=subtitle, font=F(12), text_color=C["muted"]).grid(
            row=1, column=0, sticky="e", padx=32, pady=(0, 12))
        return p

    def _build_home(self, parent):
        p = self._page(parent, "التحكم في الشبكة",
                       "تبديل فوري بدون قطع أي اتصال، والمحوّلان متصلان دائماً")

        # بطاقة الحالة
        hero = Card(p)
        hero.grid(row=2, column=0, sticky="ew", padx=32)
        hero.grid_columnconfigure(1, weight=1)
        right = ctk.CTkFrame(hero, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=22, pady=14)
        ctk.CTkLabel(right, text="الاتصال الحالي", font=F(12), text_color=C["muted"]).pack(anchor="e")
        self.hero_title = ctk.CTkLabel(right, text="جاري الفحص…", font=F(22, "bold"), text_color=C["text"])
        self.hero_title.pack(anchor="e")
        self.hero_sub = ctk.CTkLabel(right, text="", font=F(12), text_color=C["muted"])
        self.hero_sub.pack(anchor="e")

        left = ctk.CTkFrame(hero, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=22, pady=14)
        self.lat_inet = Pill(left, "الإنترنت  —")
        self.lat_inet.pack(anchor="w", pady=3)
        self.lat_intra = Pill(left, "الداخلية  —")
        self.lat_intra.pack(anchor="w", pady=3)
        rb = ctk.CTkButton(left, text="↻  تحديث", width=90, height=28, font=F(11), corner_radius=8,
                           fg_color=C["card2"], hover_color=C["hover"], text_color=C["muted"],
                           command=self.refresh_now)
        rb.pack(anchor="w", pady=(6, 0))

        # بطاقات الأوضاع
        ctk.CTkLabel(p, text="اختر وضع الاتصال", font=F(14, "bold"), text_color=C["text"]).grid(
            row=3, column=0, sticky="e", padx=32, pady=(16, 6))
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.grid(row=4, column=0, sticky="ew", padx=26)
        self.mode_cards = {}
        for i, m in enumerate(["hybrid", "intranet", "internet"]):   # من اليمين: الإنترنت أولاً
            row.grid_columnconfigure(i, weight=1, uniform="m")
            mc = ModeCard(row, m, self.request_mode)
            mc.grid(row=0, column=i, sticky="nsew", padx=6)
            self.mode_cards[m] = mc

        # بطاقات المحوّلات
        ctk.CTkLabel(p, text="المحوّلات", font=F(14, "bold"), text_color=C["text"]).grid(
            row=5, column=0, sticky="e", padx=32, pady=(16, 6))
        ar = ctk.CTkFrame(p, fg_color="transparent")
        ar.grid(row=6, column=0, sticky="ew", padx=26)
        ar.grid_columnconfigure((0, 1), weight=1, uniform="a")
        self.card_intra = AdapterCard(ar, "intranet")
        self.card_intra.grid(row=0, column=0, sticky="nsew", padx=6)
        self.card_inet = AdapterCard(ar, "internet")
        self.card_inet.grid(row=0, column=1, sticky="nsew", padx=6)

        ctk.CTkLabel(p, text="اختصارات:  Ctrl+1 الإنترنت   •   Ctrl+2 الداخلية   •   Ctrl+3 المزدوج   •   F5 تحديث",
                     font=F(10), text_color=C["faint"]).grid(row=7, column=0, sticky="e", padx=32, pady=(14, 0))
        return p

    def _field(self, parent, row, label, widget, hint=""):
        ctk.CTkLabel(parent, text=label, font=F(12, "bold"), text_color=C["text"]).grid(
            row=row, column=1, sticky="ne", padx=(10, 20), pady=(14, 0))
        widget.grid(row=row, column=0, sticky="ew", padx=(20, 0), pady=(12, 0))
        if hint:
            ctk.CTkLabel(parent, text=hint, font=F(10), text_color=C["faint"]).grid(row=row + 1, column=0, sticky="e", padx=(20, 0))

    def _build_settings(self, parent):
        p = self._page(parent, "الإعدادات", "حدّد المحوّلات وخيارات الوضع المزدوج")
        card = Card(p)
        card.grid(row=2, column=0, sticky="ew", padx=32)
        card.grid_columnconfigure(0, weight=1)

        cb_kw = dict(height=36, font=F(12), dropdown_font=F(12), corner_radius=8, justify="right",
                     fg_color=C["card2"], border_color=C["border"], button_color=C["border"],
                     button_hover_color=C["hover"], state="readonly")
        en_kw = dict(height=36, font=ctk.CTkFont(family="Consolas", size=12), corner_radius=8,
                     fg_color=C["card2"], border_color=C["border"], justify="right")

        self.cb_inet = ctk.CTkComboBox(card, values=[""], **cb_kw)
        self._field(card, 0, "محوّل الإنترنت", self.cb_inet)
        self.cb_intra = ctk.CTkComboBox(card, values=[""], **cb_kw)
        self._field(card, 2, "محوّل الشبكة الداخلية", self.cb_intra)
        self.en_gw = ctk.CTkEntry(card, placeholder_text="تُقرأ تلقائياً — أدخلها فقط إن لم تظهر", **en_kw)
        self._field(card, 4, "بوابة الشبكة الداخلية", self.en_gw,
                    "مثال: 10.32.0.1 — مطلوبة إن كانت الشبكة الداخلية بدون بوابة افتراضية")
        self.en_subnets = ctk.CTkEntry(card, **en_kw)
        self._field(card, 6, "نطاقات الشبكة الداخلية", self.en_subnets,
                    "للوضع المزدوج: عناوين تمر عبر الشبكة الداخلية، مفصولة بفاصلة")
        self.en_domain = ctk.CTkEntry(card, placeholder_text="مثال: dtw.local  (اختياري)", **en_kw)
        self._field(card, 8, "نطاق أسماء الشبكة الداخلية", self.en_domain,
                    "للوضع المزدوج: أسماء هذا النطاق تُحَل عبر DNS الداخلية")

        self.sw_auto = ctk.CTkSwitch(card, text="التشغيل تلقائياً مع ويندوز (بدون نافذة UAC)",
                                     font=F(12), progress_color=C["inet"],
                                     command=self._toggle_autostart)
        self.sw_auto.grid(row=10, column=0, columnspan=2, sticky="e", padx=20, pady=(18, 4))

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.grid(row=11, column=0, columnspan=2, sticky="ew", padx=20, pady=(14, 18))
        ctk.CTkButton(btns, text="حفظ", width=110, height=36, font=F(12, "bold"), corner_radius=8,
                      fg_color=C["inet"], hover_color="#0EA5E9", text_color="#04111D",
                      command=self.save_settings).pack(side="right")
        ctk.CTkButton(btns, text="اكتشاف تلقائي", width=130, height=36, font=F(12), corner_radius=8,
                      fg_color=C["card2"], hover_color=C["hover"], border_width=1,
                      border_color=C["border"], command=self.auto_detect).pack(side="right", padx=8)
        ctk.CTkButton(btns, text="استعادة إعدادات ويندوز الافتراضية", height=36, font=F(12),
                      corner_radius=8, fg_color="transparent", hover_color=C["hover"],
                      text_color=C["warn"], command=self.reset_windows).pack(side="left")

        info = Card(p, fg_color=C["side"])
        info.grid(row=3, column=0, sticky="ew", padx=32, pady=(14, 0))
        ctk.CTkLabel(info, text="كيف يعمل التبديل؟", font=F(12, "bold"),
                     text_color=C["text"]).pack(padx=18, pady=(12, 2), anchor="e")
        for line in ("البرنامج لا يعطّل أي محوّل",
                     "يغيّر فقط أولوية المسار، فيصبح المحوّل المختار هو الطريق الرئيسي",
                     "المحوّل الآخر يبقى متصلاً في الخلفية",
                     "زر الاستعادة يعيد أولوية ويندوز التلقائية ويحذف مسارات البرنامج"):
            ctk.CTkLabel(info, text=line + "  •", font=F(11), text_color=C["muted"]).pack(
                padx=18, anchor="e")
        ctk.CTkFrame(info, fg_color="transparent", height=8).pack()
        return p

    def _build_log(self, parent):
        p = self._page(parent, "سجل العمليات", f"يُحفظ أيضاً في: {LOG_FILE}")
        p.grid_rowconfigure(2, weight=1)
        self.log_box = ctk.CTkTextbox(p, font=ctk.CTkFont(family="Consolas", size=12), fg_color=C["card"],
                                      border_width=1, border_color=C["border"], corner_radius=12,
                                      text_color=C["muted"], wrap="word")
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=32)
        for tag, col in [("info", C["muted"]), ("success", C["ok"]), ("error", C["err"]),
                         ("warning", C["warn"]), ("title", C["gold"])]:
            self.log_box.tag_config(tag, foreground=col)
        self.log_box.configure(state="disabled")
        bar = ctk.CTkFrame(p, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", padx=32, pady=14)
        ctk.CTkButton(bar, text="مسح", width=90, height=32, font=F(12), corner_radius=8,
                      fg_color=C["card2"], hover_color=C["hover"], command=self._clear_log).pack(side="right")
        ctk.CTkButton(bar, text="نسخ تقرير التشخيص", width=150, height=32, font=F(12, "bold"),
                      corner_radius=8, fg_color=C["inet"], hover_color="#0EA5E9", text_color="#04111D",
                      command=self.copy_diagnostics).pack(side="left")
        if IS_WIN:
            ctk.CTkButton(bar, text="فتح مجلد السجل", width=130, height=32, font=F(12), corner_radius=8,
                          fg_color=C["card2"], hover_color=C["hover"],
                          command=lambda: os.startfile(DATA_DIR)).pack(side="right", padx=8)
        return p

    def show_page(self, key):
        for k, pg in self.pages.items():
            pg.grid_forget()
            self.nav[k].configure(fg_color="transparent", text_color=C["muted"])
        self.pages[key].grid(row=0, column=0, sticky="nsew")
        self.nav[key].configure(fg_color=C["card2"], text_color=C["text"])
        if key == "settings":
            self._fill_settings()
        self.toast.lift()

    # ── السجل والإشعارات ────────────────────────────────────────────────────
    def log_ui(self, msg, level="info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        log.info(f"[{level}] {msg}")

        def ins():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"[{ts}]  {msg}\n", level)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.ui(ins)

    def notify(self, msg, level="info"):
        self.log_ui(msg, level)
        self.ui(lambda: self.toast.show(msg, level))

    def copy_diagnostics(self):
        def work():
            rep = (f"{APP_NAME} v{VERSION}\nconfig: {json.dumps(self.cfg, ensure_ascii=False)}\n\n"
                   + self.backend.diagnostics())
            def put():
                self.clipboard_clear()
                self.clipboard_append(rep)
            self.ui(put)
            self.notify("نُسخ تقرير التشخيص — الصقه في المحادثة", "success")
        self.notify("جاري جمع تقرير التشخيص…", "info")
        threading.Thread(target=work, daemon=True).start()

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # تحديثات الواجهة من الخيوط الخلفية تمر عبر طابور (آمن مع Tk)
    def ui(self, fn):
        self._ui_q.put(fn)

    def _pump(self):
        try:
            while True:
                self._ui_q.get_nowait()()
        except queue.Empty:
            pass
        except Exception as e:
            log.exception(f"ui error: {e}")
        self.after(50, self._pump)

    # ── قراءة الحالة ────────────────────────────────────────────────────────
    def _adapter(self, name):
        if not self.snap or not name:
            return None
        return next((a for a in self.snap["adapters"] if a["name"] == name), None)

    def intra_gw(self, na=None):
        na = na or self._adapter(self.cfg.get("intranet_if"))
        return (na or {}).get("gw") or self.cfg.get("intranet_gw", "")

    def refresh_now(self):
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _poll(self):
        if not self.busy:
            self.refresh_now()
        self.after(self.POLL_MS, self._poll)

    def _refresh_worker(self, wait=False):
        # wait=True: انتظر انتهاء التحديث الجاري (حتى 6 ث) بدل التخطّي
        got = self._snap_lock.acquire(timeout=6) if wait else self._snap_lock.acquire(blocking=False)
        if not got:
            return
        try:
            snap = self.backend.snapshot(intra_ping=self.intra_gw())
            if not snap:
                self.ui(lambda: self.hero_title.configure(text="تعذّر قراءة حالة الشبكة"))
                return
            self.snap = snap
            first = self._first_snap
            self._first_snap = False
            names = {a["name"] for a in snap["adapters"]}
            if first and (not self.cfg.get("internet_if") or not self.cfg.get("intranet_if")
                          or self.cfg.get("internet_if") not in names
                          or self.cfg.get("intranet_if") not in names):
                self._detect_worker(silent=True)
            # إعادة تفعيل محوّل تركه الإصدار السابق معطّلاً (المحوّلان يجب أن يبقيا متصلين)
            if first and self.admin:
                dis = [a for a in snap["adapters"]
                       if a["name"] in (self.cfg.get("internet_if"), self.cfg.get("intranet_if"))
                       and (a.get("status") or "").lower() == "disabled"]
                if dis:
                    self.log_ui("إعادة تفعيل: " + "، ".join(a["name"] for a in dis), "warning")
                    self.backend.enable([a["index"] for a in dis])
                    snap = self.backend.snapshot(intra_ping=self.intra_gw()) or snap
                    self.snap = snap
                    self.notify("أُعيد تفعيل " + "، ".join(a["name"] for a in dis), "success")
            for a in snap["adapters"]:
                if a["name"] == self.cfg.get("intranet_if") and not a.get("gw"):
                    a["gw_manual"] = self.cfg.get("intranet_gw", "")
            self.ui(self._render)
            # بعد إعادة التشغيل تختفي مسارات الوضع المزدوج المؤقتة → إعادة تطبيقها بصمت
            if first and self.cfg.get("mode") == "hybrid" and self.admin:
                self.ui(lambda: self.request_mode("hybrid", force=True, quiet=True))
        finally:
            self._snap_lock.release()

    def current_mode(self):
        """الوضع الفعلي حسب جدول التوجيه (وليس فقط ما حُفظ)"""
        if not self.snap:
            return None
        best = self.snap.get("best")
        ia = self._adapter(self.cfg.get("internet_if"))
        na = self._adapter(self.cfg.get("intranet_if"))
        saved = self.cfg.get("mode")
        if ia and best == ia["index"]:
            return "hybrid" if saved == "hybrid" else "internet"
        if na and best == na["index"]:
            return "intranet"
        return None

    def _render(self):
        if not self.snap:
            return
        mode = self.current_mode()
        ia = self._adapter(self.cfg.get("internet_if"))
        na = self._adapter(self.cfg.get("intranet_if"))
        best = self.snap.get("best")
        primary = next((a for a in self.snap["adapters"] if a["index"] == best), None)

        for m, card in self.mode_cards.items():
            card.set_active(m == mode)
            card.set_enabled(self.admin)
        if mode:
            meta = MODE_META[mode]
            if mode not in self._hero_icons:
                self._hero_icons[mode] = draw_icon(mode, meta["color"], 26)
            self.hero_title.configure(text=meta["title"] + "  ", text_color=meta["color"],
                                      image=self._hero_icons[mode], compound="right")
        else:
            self.hero_title.configure(text="إعدادات ويندوز التلقائية", text_color=C["text"], image=None)
        if primary:
            self.hero_sub.configure(text=f"المسار الرئيسي عبر  {primary['name']}  •  {primary.get('ip') or '—'}")
        else:
            self.hero_sub.configure(text="لا يوجد مسار افتراضي (غير متصل)")

        im, nm = self.snap.get("inet_ms", -1), self.snap.get("intra_ms", -1)
        self.lat_inet.set(f"● الإنترنت  {im} ms" if im >= 0 else "● الإنترنت  غير متاح",
                          C["ok"] if im >= 0 else C["err"])
        if na and self.intra_gw(na):
            self.lat_intra.set(f"● الداخلية  {nm} ms" if nm >= 0 else "● الداخلية  غير متاحة",
                               C["ok"] if nm >= 0 else C["err"])
        else:
            self.lat_intra.set("● الداخلية  —", C["muted"])

        self.card_inet.update_from(ia, ia is not None and best == ia["index"])
        self.card_intra.update_from(na, na is not None and best == na["index"])

    # ── التبديل ─────────────────────────────────────────────────────────────
    def request_mode(self, mode, force=False, quiet=False):
        if self.busy:
            return
        if not self.admin:
            self.notify("التبديل يحتاج صلاحيات المدير — أعد تشغيل البرنامج كمسؤول", "error")
            return
        if not force and self.current_mode() == mode:
            self.ui(lambda: self.toast.show(f"{MODE_META[mode]['title']} مفعّل بالفعل", "info", 1800))
            return
        ia = self._adapter(self.cfg.get("internet_if"))
        na = self._adapter(self.cfg.get("intranet_if"))
        need = {"internet": [ia], "intranet": [na], "hybrid": [ia, na]}[mode]
        if any(a is None for a in need):
            self.notify("حدّد المحوّلات أولاً من صفحة الإعدادات", "warning")
            self.show_page("settings")
            return
        subnets = []
        if mode == "hybrid":
            subnets = [s.strip() for s in self.cfg.get("intranet_subnets", "").split(",") if s.strip()]
            bad = [s for s in subnets if not _CIDR_RE.match(s)]
            if bad or not subnets:
                self.notify(f"نطاقات غير صالحة: {', '.join(bad) or '(فارغة)'}", "error")
                self.show_page("settings")
                return
        gw = self.intra_gw(na) if na else ""
        if mode in ("intranet", "hybrid"):
            if (na.get("status") or "").lower() == "disconnected":
                self.notify(f"كابل الشبكة الداخلية غير موصول ({na['name']})", "error")
                return
            if not _IP_RE.match(gw or ""):
                self.notify("الشبكة الداخلية بلا بوابة — أدخل «بوابة الشبكة الداخلية» في الإعدادات", "warning")
                self.show_page("settings")
                return
        enable = [a["index"] for a in (ia, na) if a and (a.get("status") or "").lower() == "disabled"]

        self.busy = True
        self.mode_cards[mode].set_busy(True)
        for c in self.mode_cards.values():
            c.set_enabled(False)
        payload = {
            "mode": mode,
            "inet": ia["index"] if ia else 0,
            "intra": na["index"] if na else 0,
            "intra_gw": gw,
            "gw_route": gw if (na and not na.get("gw")) else "",
            "enable": enable,
            "subnets": subnets,
            "domain": self.cfg.get("intranet_domain", "").strip().lstrip("."),
            "dns": (na or {}).get("dns", []),
            "remove": self.cfg.get("added_routes", []),
        }
        if payload["domain"]:
            payload["domain"] = "." + payload["domain"]
        if not quiet:
            self.log_ui(f"التبديل إلى: {MODE_META[mode]['title']}…", "info")
        threading.Thread(target=self._apply_worker, args=(mode, payload, quiet), daemon=True).start()

    def _apply_worker(self, mode, payload, quiet):
        t0 = time.time()
        try:
            res = self.backend.apply(payload)
            with _CFG_LOCK:
                self.cfg["added_routes"] = res.get("added", [])
            expected = payload["intra"] if mode == "intranet" else payload["inet"]
            ok = res.get("best") == expected
            if ok:
                self.cfg["mode"] = mode
            save_cfg(self.cfg)
            for e in res.get("errors", []):
                self.log_ui(f"تنبيه: {e}", "warning")
            dt = time.time() - t0
            if ok and not quiet:
                self.notify(f"تم التبديل إلى {MODE_META[mode]['title']}  ({dt:.1f} ث)", "success")
            elif not ok:
                ist = (res.get("intra_status") or "").lower()
                if mode in ("intranet", "hybrid") and ist and ist != "up":
                    self.notify(f"محوّل الشبكة الداخلية غير متصل (الحالة: {res.get('intra_status')})", "error")
                else:
                    self.notify("لم يتغيّر المسار — انسخ تقرير التشخيص من صفحة السجل", "error")
        except Exception as e:
            log.exception("apply")
            self.notify(f"خطأ أثناء التبديل: {e}", "error")
        finally:
            def done():
                self.busy = False
                self.mode_cards[mode].set_busy(False)
                for c in self.mode_cards.values():
                    c.set_enabled(self.admin)
            self.ui(done)
            self._refresh_worker_wait()

    def _refresh_worker_wait(self):
        # تحديث فوري بعد التبديل (ننتظر إن كان تحديث آخر قيد التنفيذ)
        self._refresh_worker(wait=True)

    def reset_windows(self):
        if self.busy:
            return
        if not self.admin:
            self.notify("هذه العملية تحتاج صلاحيات المدير", "error")
            return
        ia = self._adapter(self.cfg.get("internet_if"))
        na = self._adapter(self.cfg.get("intranet_if"))
        payload = {"mode": "reset", "inet": (ia or {}).get("index", 0), "intra": (na or {}).get("index", 0),
                   "intra_gw": "", "gw_route": "", "enable": [], "subnets": [], "domain": "", "dns": [],
                   "remove": self.cfg.get("added_routes", [])}
        self.busy = True

        def work():
            try:
                self.backend.apply(payload)
                self.cfg["added_routes"] = []
                self.cfg["mode"] = ""
                save_cfg(self.cfg)
                self.notify("تمت استعادة الأولوية التلقائية لويندوز", "success")
            finally:
                self.busy = False
                self._refresh_worker_wait()
        threading.Thread(target=work, daemon=True).start()

    # ── الإعدادات ───────────────────────────────────────────────────────────
    def _fill_settings(self):
        names = [a["name"] for a in (self.snap or {}).get("adapters", [])] or [""]
        for cb, key in ((self.cb_inet, "internet_if"), (self.cb_intra, "intranet_if")):
            cb.configure(values=names)
            cb.set(self.cfg.get(key, ""))
        self.en_subnets.delete(0, "end")
        self.en_subnets.insert(0, self.cfg.get("intranet_subnets", ""))
        self.en_gw.delete(0, "end")
        if self.cfg.get("intranet_gw"):
            self.en_gw.insert(0, self.cfg["intranet_gw"])
        self.en_domain.delete(0, "end")
        if self.cfg.get("intranet_domain"):
            self.en_domain.insert(0, self.cfg["intranet_domain"])
        threading.Thread(target=lambda: (lambda on: self.ui(
            lambda: self.sw_auto.select() if on else self.sw_auto.deselect()))(
            self.backend.autostart_enabled()), daemon=True).start()

    def save_settings(self):
        inet, intra = self.cb_inet.get().strip(), self.cb_intra.get().strip()
        if inet and inet == intra:
            self.notify("لا يمكن اختيار نفس المحوّل للشبكتين", "error")
            return
        subnets = [s.strip() for s in self.en_subnets.get().split(",") if s.strip()]
        bad = [s for s in subnets if not _CIDR_RE.match(s)]
        if bad:
            self.notify(f"نطاق غير صالح: {bad[0]}", "error")
            return
        gw = self.en_gw.get().strip()
        if gw and not _IP_RE.match(gw):
            self.notify(f"بوابة غير صالحة: {gw}", "error")
            return
        self.cfg["intranet_gw"] = gw
        self.cfg.update({"internet_if": inet, "intranet_if": intra,
                         "intranet_subnets": ", ".join(subnets),
                         "intranet_domain": self.en_domain.get().strip()})
        save_cfg(self.cfg)
        self.notify("تم حفظ الإعدادات", "success")
        self.refresh_now()

    def _toggle_autostart(self):
        on = bool(self.sw_auto.get())

        def work():
            ok = self.backend.set_autostart(on)
            if ok:
                self.notify("سيعمل البرنامج تلقائياً مع ويندوز" if on else "أُلغي التشغيل التلقائي", "success")
            else:
                self.notify("تعذّر تغيير التشغيل التلقائي (يحتاج صلاحيات المدير)", "error")
                self.ui(lambda: self.sw_auto.deselect() if on else self.sw_auto.select())
        threading.Thread(target=work, daemon=True).start()

    def auto_detect(self):
        threading.Thread(target=self._detect_worker, daemon=True).start()

    def _detect_worker(self, silent=False):
        snap = self.snap or self.backend.snapshot()
        if not snap:
            self.notify("تعذّر قراءة المحوّلات", "error")
            return
        ads = snap["adapters"]
        cands = [a for a in ads if a.get("up") and a.get("ip") and a.get("gw")]
        self.log_ui("اكتشاف: فحص الإنترنت لكل محوّل…", "info")
        net = self.backend.internet_by_source([a["ip"] for a in cands])
        inet_c = [a for a in cands if net.get(a["ip"])]
        inet_c.sort(key=lambda a: (0 if a["is_wifi"] else 1))
        inet = inet_c[0] if inet_c else next((a for a in cands if a["is_wifi"]), None)
        # الداخلية: أي محوّل آخر — متصل (حتى بلا بوابة)، ثم معطّل، ثم بلا كابل
        def rank(a):
            st = (a.get("status") or "").lower()
            return (0 if (a.get("up") and a.get("ip")) else 1 if st == "disabled" else 2,
                    0 if not a["is_wifi"] else 1,
                    0 if a.get("gw") else 1,
                    0 if "ethernet" in (a["name"] + a.get("desc", "")).lower() else 1)
        if not inet:   # لا إنترنت مؤكد: الوايفي (بأي حالة) هو محوّل الإنترنت
            inet = next((a for a in sorted(ads, key=lambda a: 0 if a.get("up") else 1) if a["is_wifi"]), None)
        rest = sorted([a for a in ads if a is not inet], key=rank)
        intra = rest[0] if rest else None
        with _CFG_LOCK:
            self.cfg["internet_if"] = inet["name"] if inet else ""
            self.cfg["intranet_if"] = intra["name"] if intra else ""
        save_cfg(self.cfg)
        msg = f"الإنترنت: {self.cfg['internet_if'] or '—'}   •   الداخلية: {self.cfg['intranet_if'] or '—'}"
        if silent:
            self.log_ui("اكتشاف تلقائي — " + msg, "success")
        else:
            self.notify("اكتشاف — " + msg, "success")
            self.ui(self._fill_settings)
        self.ui(self._render)


# ══════════════════════════════════════════════════════════════════════════════
def single_instance():
    """نسخة واحدة فقط — إن كان البرنامج يعمل نُظهر نافذته بدل فتح نسخة ثانية"""
    if not IS_WIN:
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.CreateMutexW(None, False, "Global\\DTW_NetworkSwitcher_v8")
        if k.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            u = ctypes.windll.user32
            h = u.FindWindowW(None, f"{APP_NAME} — DTW ELBAYADH")
            if h:
                u.ShowWindow(h, 9)
                u.SetForegroundWindow(h)
            return False
    except Exception:
        pass
    return True


def ensure_admin():
    """عند التشغيل كسكربت: إعادة التشغيل كمسؤول. (ملف exe يطلبها عبر manifest)"""
    if not IS_WIN or is_admin() or getattr(sys, "frozen", False) or "--no-elevate" in sys.argv:
        return
    try:
        import ctypes
        exe = pythonw_path()
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, f'"{os.path.abspath(__file__)}"', None, 1)
        if rc > 32:
            sys.exit(0)
    except Exception as e:
        log.error(f"elevate: {e}")


if __name__ == "__main__":
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    ensure_admin()
    if single_instance():
        App().mainloop()
