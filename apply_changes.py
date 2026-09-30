import re

file_path = "frontend/index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update font link to include Manrope
font_old = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">'
font_new = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Manrope:wght@600;700;800;900&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">'
if font_old in content:
    content = content.replace(font_old, font_new)

# 2. Use local tailwind.cdn.js if cdn.tailwindcss.com exists
content = content.replace('<script src="https://cdn.tailwindcss.com"></script>', '<script src="tailwind.cdn.js"></script>')

# 3. CSS variables for header background in light and dark
var_light_old = '--header-bg: rgba(255, 255, 255, 0.82);'
var_light_new = '''--header-bg: rgba(218, 224, 233, 0.85);
      --header-border: rgba(195, 205, 218, 0.85);'''
content = content.replace(var_light_old, var_light_new)

var_dark_old = '--header-bg: rgba(6, 12, 20, 0.82);'
var_dark_new = '''--header-bg: rgba(6, 12, 20, 0.75);
      --header-border: rgba(255, 255, 255, 0.08);'''
content = content.replace(var_dark_old, var_dark_new)

# 4. Inject Typography + Red Gradient + Animations into <style>
custom_css = """
    /* --------------------------------------------------------------------------
       TYPOGRAPHY SPECIFICATION (Citizen Web Page):
       - Heading: Manrope Bold
       - Body: Inter Regular
       - Buttons: Inter SemiBold
       -------------------------------------------------------------------------- */
    h1, h2, h3, h4, h5, h6, .font-heading,
    [class*="text-xl"].font-bold, [class*="text-2xl"].font-bold,
    [class*="text-3xl"].font-bold, [class*="text-4xl"].font-bold,
    [class*="text-5xl"].font-bold, [class*="text-6xl"].font-bold,
    [class*="text-7xl"].font-bold, [class*="font-black"],
    [class*="font-extrabold"] {
      font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      font-weight: 700 !important;
      letter-spacing: -0.02em;
    }

    body, p, span, div, input, select, textarea, label, td, th {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-weight: 400;
    }

    button, .btn, [role="button"], [class*="k-btn"], [id*="-btn"], [id*="-tab-btn"] {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      font-weight: 600 !important;
      letter-spacing: -0.01em;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    button:hover:not(:disabled), .btn:hover:not(:disabled) {
      filter: brightness(1.08);
      transform: translateY(-1px);
    }

    button:active:not(:disabled), .btn:active:not(:disabled) {
      transform: translateY(0) scale(0.98);
    }

    .font-mono, [class*="font-mono"], code, pre {
      font-family: 'JetBrains Mono', monospace !important;
    }

    .k-header {
      background-color: var(--header-bg) !important;
      backdrop-filter: blur(24px) saturate(180%) !important;
      -webkit-backdrop-filter: blur(24px) saturate(180%) !important;
      border-bottom: 1px solid var(--header-border) !important;
      box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.08);
    }

    /* --------------------------------------------------------------------------
       LEFT ELEMENT: VIBRANT RED GRADIENT BACKGROUND & ANIMATIONS
       -------------------------------------------------------------------------- */
    /* Dark Mode: Deep crimson emergency red gradient with AAA white text contrast */
    html.dark #card-threat-gauge, html.dark .card-threat-ambient {
      background: linear-gradient(135deg, #7f1d1d 0%, #5c0f1e 40%, #1e1122 80%, #0b131e 100%) !important;
      border: 1px solid rgba(255, 69, 105, 0.5) !important;
      box-shadow: 0 12px 38px -5px rgba(185, 28, 28, 0.45), 0 0 25px rgba(255, 45, 85, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.18) !important;
      position: relative;
      overflow: hidden;
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease, border-color 0.3s ease !important;
    }

    /* Light Mode: Atmospheric radiant soft coral-to-rose red gradient with AAA dark text contrast */
    :root #card-threat-gauge, :root .card-threat-ambient {
      background: linear-gradient(135deg, #fee2e2 0%, #fecaca 35%, #fff1f2 70%, #ffffff 100%) !important;
      border: 1px solid rgba(239, 68, 68, 0.45) !important;
      box-shadow: 0 10px 32px -4px rgba(220, 38, 38, 0.20), 0 4px 16px rgba(0, 0, 0, 0.05) !important;
      position: relative;
      overflow: hidden;
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease, border-color 0.3s ease !important;
    }

    /* Contrast Helpers for Maximum Text Clarity in Both Modes */
    html.dark #card-threat-gauge #hero-temp-feels, html.dark .card-threat-ambient #hero-temp-feels {
      color: #ffffff !important;
    }
    :root #card-threat-gauge #hero-temp-feels, :root .card-threat-ambient #hero-temp-feels {
      color: #881337 !important;
    }
    html.dark #card-threat-gauge #lbl-feels-like, html.dark .card-threat-ambient #lbl-feels-like {
      color: #ffffff !important;
    }
    :root #card-threat-gauge #lbl-feels-like, :root .card-threat-ambient #lbl-feels-like {
      color: #881337 !important;
    }
    html.dark #card-threat-gauge #hero-desc, html.dark .card-threat-ambient #hero-desc {
      color: #f1f5f9 !important;
    }
    :root #card-threat-gauge #hero-desc, :root .card-threat-ambient #hero-desc {
      color: #1e293b !important;
    }
    html.dark #card-threat-gauge #lbl-wbgt-method, html.dark .card-threat-ambient #lbl-wbgt-method {
      color: #fecdd3 !important;
    }
    :root #card-threat-gauge #lbl-wbgt-method, :root .card-threat-ambient #lbl-wbgt-method {
      color: #9f1239 !important;
    }
    html.dark #card-threat-gauge #txt-thermal-debt-pct, html.dark .card-threat-ambient #txt-thermal-debt-pct {
      color: #ffffff !important;
    }
    :root #card-threat-gauge #txt-thermal-debt-pct, :root .card-threat-ambient #txt-thermal-debt-pct {
      color: #881337 !important;
    }
    html.dark #card-threat-gauge #lbl-thermal-debt, html.dark .card-threat-ambient #lbl-thermal-debt {
      color: #fecdd3 !important;
    }
    :root #card-threat-gauge #lbl-thermal-debt, :root .card-threat-ambient #lbl-thermal-debt {
      color: #9f1239 !important;
    }
    html.dark #card-threat-gauge #lbl-cardiac-reset, html.dark .card-threat-ambient #lbl-cardiac-reset {
      color: #fecdd3 !important;
    }
    :root #card-threat-gauge #lbl-cardiac-reset, :root .card-threat-ambient #lbl-cardiac-reset {
      color: #9f1239 !important;
    }
    html.dark #card-threat-gauge .pill-stat-card, html.dark .card-threat-ambient .pill-stat-card {
      background: rgba(15, 23, 42, 0.65) !important;
      border-color: rgba(255, 255, 255, 0.15) !important;
      color: #ffffff !important;
      backdrop-filter: blur(8px);
    }
    :root #card-threat-gauge .pill-stat-card, :root .card-threat-ambient .pill-stat-card {
      background: rgba(255, 255, 255, 0.90) !important;
      border-color: rgba(239, 68, 68, 0.30) !important;
      color: #0f172a !important;
      backdrop-filter: blur(8px);
    }
    html.dark #card-threat-gauge #btn-what-should-i-do, html.dark .card-threat-ambient #btn-what-should-i-do {
      background-color: #ffffff !important;
      color: #020617 !important;
    }
    :root #card-threat-gauge #btn-what-should-i-do, :root .card-threat-ambient #btn-what-should-i-do {
      background-color: #0f172a !important;
      color: #ffffff !important;
    }
    html.dark #card-threat-gauge #btn-why-risk-critical, html.dark .card-threat-ambient #btn-why-risk-critical {
      background-color: rgba(0, 0, 0, 0.35) !important;
      color: #ffffff !important;
      border-color: rgba(255, 255, 255, 0.25) !important;
    }
    :root #card-threat-gauge #btn-why-risk-critical, :root .card-threat-ambient #btn-why-risk-critical {
      background-color: rgba(255, 255, 255, 0.9) !important;
      color: #881337 !important;
      border-color: rgba(239, 68, 68, 0.4) !important;
    }
    html.dark #card-threat-gauge #gauge-track-circle, html.dark .card-threat-ambient #gauge-track-circle {
      stroke: rgba(15, 23, 42, 0.7) !important;
    }
    :root #card-threat-gauge #gauge-track-circle, :root .card-threat-ambient #gauge-track-circle {
      stroke: rgba(254, 202, 202, 0.8) !important;
    }

    /* Left Card Heat Aura Breathing Animation (Living Thermal Mesh) */
    #card-threat-gauge::before, .card-threat-ambient::before {
      content: '';
      position: absolute;
      top: -35%;
      left: -35%;
      width: 170%;
      height: 170%;
      background: radial-gradient(circle at 25% 25%, rgba(239, 68, 68, 0.28), transparent 55%);
      animation: threatAuraBreathe 5.5s ease-in-out infinite alternate;
      pointer-events: none;
      z-index: 1;
    }

    @keyframes threatAuraBreathe {
      0% { transform: scale(0.96) translate(0, 0); opacity: 0.55; }
      50% { transform: scale(1.05) translate(12px, -8px); opacity: 0.85; }
      100% { transform: scale(0.98) translate(-6px, 10px); opacity: 0.60; }
    }

    #card-threat-gauge:hover, .card-threat-ambient:hover {
      transform: translateY(-4px);
      box-shadow: 0 20px 48px -6px rgba(185, 28, 28, 0.55), 0 0 35px rgba(255, 45, 85, 0.35) !important;
      border-color: rgba(255, 69, 105, 0.8) !important;
    }

    /* Heartbeat animation for Level 4 Risk Badge */
    .badge-threat-pulse {
      animation: badgeHeartbeat 2.4s ease-in-out infinite;
    }
    @keyframes badgeHeartbeat {
      0%, 100% { transform: scale(1); filter: brightness(1); }
      14% { transform: scale(1.06); filter: brightness(1.2); }
      28% { transform: scale(1); filter: brightness(1); }
      42% { transform: scale(1.08); filter: brightness(1.25); }
      70% { transform: scale(1); filter: brightness(1); }
    }

    /* SVG Radial Gauge Ring Pulse */
    .gauge-circle-pulse {
      filter: drop-shadow(0 0 8px rgba(255, 45, 85, 0.65));
      animation: gaugeRingPulse 3s ease-in-out infinite;
    }
    @keyframes gaugeRingPulse {
      0%, 100% { filter: drop-shadow(0 0 6px rgba(255, 45, 85, 0.5)); stroke-width: 11; }
      50% { filter: drop-shadow(0 0 15px rgba(255, 45, 85, 0.95)); stroke-width: 11.5; }
    }

    /* Mini Stat Pill Micro-Interaction */
    .pill-stat-card {
      transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s ease, border-color 0.22s ease !important;
    }
    .pill-stat-card:hover {
      transform: translateY(-2px);
      border-color: rgba(255, 45, 85, 0.45) !important;
      box-shadow: 0 6px 16px rgba(255, 45, 85, 0.18) !important;
    }

    /* --------------------------------------------------------------------------
       RIGHT ELEMENT: 5-DAY TRAJECTORY ANIMATIONS
       -------------------------------------------------------------------------- */
    .card-trajectory-ambient {
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease, border-color 0.3s ease !important;
    }
    .card-trajectory-ambient:hover {
      transform: translateY(-4px);
      box-shadow: 0 18px 45px -6px rgba(0, 0, 0, 0.8), 0 0 28px rgba(0, 229, 255, 0.22) !important;
      border-color: rgba(0, 229, 255, 0.42) !important;
    }

    /* Staggered Expanding Animation for 5 Progress Bars */
    @keyframes trajectoryBarGrow {
      from { width: 0 !important; opacity: 0.2; }
      to { opacity: 1; }
    }
    .bar-anim-1 { animation: trajectoryBarGrow 0.75s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both; }
    .bar-anim-2 { animation: trajectoryBarGrow 0.75s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both; }
    .bar-anim-3 { animation: trajectoryBarGrow 0.75s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both; }
    .bar-anim-4 { animation: trajectoryBarGrow 0.75s cubic-bezier(0.16, 1, 0.3, 1) 0.4s both; }
    .bar-anim-5 { animation: trajectoryBarGrow 0.75s cubic-bezier(0.16, 1, 0.3, 1) 0.5s both; }

    /* Interactive Day Row Slide on Hover */
    .trajectory-day-row {
      transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.2s ease, filter 0.2s ease;
      border-radius: 8px;
      padding: 3px 6px;
      margin: -3px -6px;
    }
    .trajectory-day-row:hover {
      transform: translateX(5px);
      background-color: rgba(255, 255, 255, 0.035);
      filter: brightness(1.1);
    }
    html:not(.dark) .trajectory-day-row:hover {
      background-color: rgba(0, 0, 0, 0.03);
    }
    .trajectory-day-row:hover .trajectory-bar-fill {
      filter: brightness(1.15) drop-shadow(0 0 8px currentColor);
      transform: scaleY(1.08);
    }

    /* Warning Banner Breathing Pulse */
    .banner-warning-pulse {
      animation: bannerWarningBreathe 3.5s ease-in-out infinite;
    }
    @keyframes bannerWarningBreathe {
      0%, 100% { border-color: rgba(255, 122, 0, 0.3); box-shadow: 0 0 0 0 rgba(255, 122, 0, 0); }
      50% { border-color: rgba(255, 122, 0, 0.65); box-shadow: 0 0 16px rgba(255, 122, 0, 0.25); }
    }
"""

if "TYPOGRAPHY SPECIFICATION" not in content:
    content = content.replace("/* Core Element Theme Bindings */", custom_css + "\n    /* Core Element Theme Bindings */")

# 5. HTML replacements for Heading, Margins, Left and Right cards
# Replace <main ...>
main_old = '<main class="max-w-7xl mx-auto px-4 lg:px-8 py-6 space-y-8">'
main_new = '<main class="max-w-7xl mx-auto px-4 lg:px-8 py-8 lg:py-14 space-y-12 lg:space-y-16">'
content = content.replace(main_old, main_new)

# Replace Title Row wrapper
title_row_old = '<div class="flex flex-col md:flex-row md:items-end justify-between gap-4 pt-1">'
title_row_new = '<div class="flex flex-col md:flex-row md:items-end justify-between gap-6 pt-2 pb-4">'
content = content.replace(title_row_old, title_row_new)

# Replace Heading & Subhead
h1_old = '<h1 id="hero-headline" class="text-3xl sm:text-5xl font-black tracking-tight k-text-main leading-tight">'
h1_new = '<h1 id="hero-headline" class="text-4xl sm:text-6xl lg:text-[4.25rem] font-black tracking-tight k-text-main leading-[1.08]">'
content = content.replace(h1_old, h1_new)

sub_old = '<p id="hero-subhead" class="k-text-sub text-xs sm:text-sm font-sans max-w-2xl">'
sub_new = '<p id="hero-subhead" class="k-text-sub text-sm sm:text-base lg:text-[1.125rem] font-sans max-w-3xl leading-relaxed mt-3">'
content = content.replace(sub_old, sub_new)

# Section B grid gap
grid_b_old = '<div id="section-hero" class="grid grid-cols-1 lg:grid-cols-12 gap-6">'
grid_b_new = '<div id="section-hero" class="grid grid-cols-1 lg:grid-cols-12 gap-8 my-2">'
content = content.replace(grid_b_old, grid_b_new)

# Left card tag
card_l_old = '<div class="lg:col-span-7 rounded-2xl k-card border p-6 shadow-xl relative overflow-hidden flex flex-col justify-between">'
card_l_new = '<div id="card-threat-gauge" class="card-threat-ambient lg:col-span-7 rounded-2xl border p-6 lg:p-7 shadow-xl relative overflow-hidden flex flex-col justify-between">'
content = content.replace(card_l_old, card_l_new)

# Left card badge
badge_old = '<span id="hero-alert-badge" class="px-2.5 py-0.5 rounded-full font-mono text-[9px] font-bold text-[#FF4D6D] bg-[#3B111A] border border-[#FF2D55]/30">LEVEL 4 · HIGH RISK</span>'
badge_new = '<span id="hero-alert-badge" class="badge-threat-pulse px-2.5 py-0.5 rounded-full font-mono text-[9px] font-bold text-[#FF4D6D] bg-[#3B111A] border border-[#FF2D55]/30">LEVEL 4 · HIGH RISK</span>'
content = content.replace(badge_old, badge_new)

# Left card pills
content = content.replace('<div class="p-2.5 rounded-xl k-card-alt border">', '<div class="pill-stat-card p-2.5 rounded-xl k-card-alt border">')

# Left card gauge ring
gauge_old = '<circle id="radial-gauge-debt" class="gauge-circle" cx="60" cy="60" r="48" fill="none" stroke="#FF2D55" stroke-width="11" stroke-dasharray="301.6" stroke-dashoffset="12" stroke-linecap="round" />'
gauge_new = '<circle id="radial-gauge-debt" class="gauge-circle gauge-circle-pulse" cx="60" cy="60" r="48" fill="none" stroke="#FF2D55" stroke-width="11" stroke-dasharray="301.6" stroke-dashoffset="12" stroke-linecap="round" />'
content = content.replace(gauge_old, gauge_new)

# Right card tag
card_r_old = '<div id="section-forecast" class="lg:col-span-5 rounded-2xl k-card border p-6 shadow-xl flex flex-col justify-between">'
card_r_new = '<div id="section-forecast" class="card-trajectory-ambient lg:col-span-5 rounded-2xl k-card border p-6 lg:p-7 shadow-xl flex flex-col justify-between">'
content = content.replace(card_r_old, card_r_new)

# Day rows & bar animations
content = content.replace('<div class="flex items-center gap-3 text-xs">\n              <span id="lbl-day-today"', '<div class="trajectory-day-row flex items-center gap-3 text-xs">\n              <span id="lbl-day-today"')
content = content.replace('<div class="absolute inset-y-0 left-0 bg-[#FF2D55] rounded-md transition-all duration-700" style="width: 92%;"></div>', '<div class="trajectory-bar-fill bar-anim-1 absolute inset-y-0 left-0 bg-[#FF2D55] rounded-md transition-all duration-700" style="width: 92%;"></div>')

content = content.replace('<div class="flex items-center gap-3 text-xs">\n              <span id="lbl-day-fri"', '<div class="trajectory-day-row flex items-center gap-3 text-xs">\n              <span id="lbl-day-fri"')
content = content.replace('<div class="absolute inset-y-0 left-0 bg-[#FF7A00] rounded-md transition-all duration-700" style="width: 84%;"></div>', '<div class="trajectory-bar-fill bar-anim-2 absolute inset-y-0 left-0 bg-[#FF7A00] rounded-md transition-all duration-700" style="width: 84%;"></div>')

content = content.replace('<div class="flex items-center gap-3 text-xs">\n              <span id="lbl-day-sat"', '<div class="trajectory-day-row flex items-center gap-3 text-xs">\n              <span id="lbl-day-sat"')
content = content.replace('<div class="absolute inset-y-0 left-0 bg-[#FF7A00] rounded-md transition-all duration-700" style="width: 78%;"></div>', '<div class="trajectory-bar-fill bar-anim-3 absolute inset-y-0 left-0 bg-[#FF7A00] rounded-md transition-all duration-700" style="width: 78%;"></div>')

content = content.replace('<div class="flex items-center gap-3 text-xs">\n              <span id="lbl-day-sun"', '<div class="trajectory-day-row flex items-center gap-3 text-xs">\n              <span id="lbl-day-sun"')
content = content.replace('<div class="absolute inset-y-0 left-0 bg-[#FFB800] rounded-md transition-all duration-700" style="width: 68%;"></div>', '<div class="trajectory-bar-fill bar-anim-4 absolute inset-y-0 left-0 bg-[#FFB800] rounded-md transition-all duration-700" style="width: 68%;"></div>')

content = content.replace('<div class="flex items-center gap-3 text-xs">\n              <span id="lbl-day-mon"', '<div class="trajectory-day-row flex items-center gap-3 text-xs">\n              <span id="lbl-day-mon"')
content = content.replace('<div class="absolute inset-y-0 left-0 bg-[#00D287] rounded-md transition-all duration-700" style="width: 52%;"></div>', '<div class="trajectory-bar-fill bar-anim-5 absolute inset-y-0 left-0 bg-[#00D287] rounded-md transition-all duration-700" style="width: 52%;"></div>')

# Warning banner pulse
banner_old = '<div class="mt-4 p-3 rounded-xl k-banner-peak border flex items-center gap-2 text-xs font-mono text-[#FF9E40]">'
banner_new = '<div class="banner-warning-pulse mt-4 p-3 rounded-xl k-banner-peak border flex items-center gap-2 text-xs font-mono text-[#FF9E40]">'
content = content.replace(banner_old, banner_new)

# Save to frontend/index.html
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

# Also save a backup to frontend/index_enhanced.html
with open("frontend/index_enhanced.html", "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: Updated frontend/index.html and created frontend/index_enhanced.html")
print("Length:", len(content))
print("card-threat-gauge in content:", "card-threat-gauge" in content)
print("lg:text-[4.25rem] in content:", "lg:text-[4.25rem]" in content)
print("banner-warning-pulse in content:", "banner-warning-pulse" in content)
