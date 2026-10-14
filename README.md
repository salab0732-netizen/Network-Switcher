<p align="center"><img src="assets/icon.png" width="128" alt="Network Switcher icon"></p>

# Network Switcher

**DTW ELBAYADH • STT • DEV2026**

تبديل سلس بين الإنترنت والشبكة الداخلية **بدون تعطيل أي محوّل**: البرنامج يغيّر أولوية المسار (Interface Metric) فقط، والمحوّلان يبقيان متصلين دائماً.

| الوضع | الوصف |
|---|---|
| 🌍 الإنترنت | كل الحركة عبر محوّل الإنترنت |
| 🏢 الشبكة الداخلية | كل الحركة عبر محوّل الشبكة الداخلية |
| ⇄ الوضع المزدوج | الإنترنت افتراضياً + نطاقات الشبكة الداخلية عبر محوّلها |

## التحميل

حمّل `NetworkSwitcher.exe` من صفحة **[Releases](../../releases/latest)** وشغّله (يطلب صلاحيات المدير).

يُبنى الملف التنفيذي تلقائياً عبر GitHub Actions عند كل تحديث على الفرع `main`.

## البناء محلياً (Windows)

انقر مرتين على `build.bat`: يبني `NetworkSwitcher.exe` ويثبّته في
`%LOCALAPPDATA%\Programs\NetworkSwitcher` ويضع اختصاراً على سطح المكتب.

## التشغيل من المصدر

```
pip install -r requirements.txt
python netswitch.py
```

اختصارات: `Ctrl+1` الإنترنت • `Ctrl+2` الداخلية • `Ctrl+3` المزدوج • `F5` تحديث
