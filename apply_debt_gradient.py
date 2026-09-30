import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add complete CSS tiers for Green, Gold, Orange, Red to <style>
tier_css = """
    /* ==========================================================================
       DYNAMIC THERMAL DEBT TIER GRADIENTS (0-10% GREEN -> 80-100% RED)
       ========================================================================== */
    #card-threat-gauge {
      transition: background 0.45s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.35s ease, box-shadow 0.35s ease !important;
    }

    /* TIER 1: GREEN SHADE (0% - 25% Thermal Debt, e.g. 0-10% Safe/Nominal) */
    html.dark #card-threat-gauge.card-threat-tier-green {
      background: linear-gradient(135deg, #064e3b 0%, #065f46 40%, #022c22 80%, #061814 100%) !important;
      border: 1px solid rgba(16, 185, 129, 0.55) !important;
      box-shadow: 0 12px 38px -5px rgba(5, 150, 105, 0.45), 0 0 25px rgba(16, 185, 129, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.18) !important;
    }
    :root #card-threat-gauge.card-threat-tier-green {
      background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 35%, #ecfdf5 70%, #ffffff 100%) !important;
      border: 1px solid rgba(16, 185, 129, 0.45) !important;
      box-shadow: 0 10px 32px -4px rgba(16, 185, 129, 0.22), 0 4px 16px rgba(0, 0, 0, 0.05) !important;
    }
    html.dark #card-threat-gauge.card-threat-tier-green #hero-temp-feels,
    html.dark #card-threat-gauge.card-threat-tier-green #lbl-feels-like,
    html.dark #card-threat-gauge.card-threat-tier-green #txt-thermal-debt-pct {
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-green #hero-temp-feels,
    :root #card-threat-gauge.card-threat-tier-green #lbl-feels-like,
    :root #card-threat-gauge.card-threat-tier-green #txt-thermal-debt-pct {
      color: #064e3b !important;
    }
    html.dark #card-threat-gauge.card-threat-tier-green #lbl-instant-threat { color: #6ee7b7 !important; }
    :root #card-threat-gauge.card-threat-tier-green #lbl-instant-threat { color: #065f46 !important; }
    html.dark #card-threat-gauge.card-threat-tier-green #lbl-wbgt-method,
    html.dark #card-threat-gauge.card-threat-tier-green #lbl-thermal-debt,
    html.dark #card-threat-gauge.card-threat-tier-green #lbl-cardiac-reset { color: #a7f3d0 !important; }
    :root #card-threat-gauge.card-threat-tier-green #lbl-wbgt-method,
    :root #card-threat-gauge.card-threat-tier-green #lbl-thermal-debt,
    :root #card-threat-gauge.card-threat-tier-green #lbl-cardiac-reset { color: #047857 !important; }
    html.dark #card-threat-gauge.card-threat-tier-green .pill-stat-card {
      background: rgba(6, 78, 59, 0.45) !important;
      border-color: rgba(16, 185, 129, 0.3) !important;
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-green .pill-stat-card {
      background: rgba(255, 255, 255, 0.9) !important;
      border-color: rgba(16, 185, 129, 0.3) !important;
      color: #064e3b !important;
    }
    :root #card-threat-gauge.card-threat-tier-green #btn-what-should-i-do {
      background-color: #064e3b !important;
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-green #btn-why-risk-critical {
      background-color: rgba(255, 255, 255, 0.9) !important;
      color: #064e3b !important;
      border-color: rgba(16, 185, 129, 0.45) !important;
    }
    :root #card-threat-gauge.card-threat-tier-green #gauge-track-circle {
      stroke: rgba(167, 243, 208, 0.7) !important;
    }

    /* TIER 2: GOLD SHADE (26% - 50% Thermal Debt, Moderate/Watch) */
    html.dark #card-threat-gauge.card-threat-tier-gold {
      background: linear-gradient(135deg, #78350f 0%, #5a2608 40%, #1e1308 80%, #0b131e 100%) !important;
      border: 1px solid rgba(245, 158, 11, 0.55) !important;
      box-shadow: 0 12px 38px -5px rgba(217, 119, 6, 0.45), 0 0 25px rgba(245, 158, 11, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.18) !important;
    }
    :root #card-threat-gauge.card-threat-tier-gold {
      background: linear-gradient(135deg, #fef3c7 0%, #fde68a 35%, #fffbeb 70%, #ffffff 100%) !important;
      border: 1px solid rgba(245, 158, 11, 0.45) !important;
      box-shadow: 0 10px 32px -4px rgba(245, 158, 11, 0.22), 0 4px 16px rgba(0, 0, 0, 0.05) !important;
    }
    html.dark #card-threat-gauge.card-threat-tier-gold #hero-temp-feels,
    html.dark #card-threat-gauge.card-threat-tier-gold #lbl-feels-like,
    html.dark #card-threat-gauge.card-threat-tier-gold #txt-thermal-debt-pct {
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-gold #hero-temp-feels,
    :root #card-threat-gauge.card-threat-tier-gold #lbl-feels-like,
    :root #card-threat-gauge.card-threat-tier-gold #txt-thermal-debt-pct {
      color: #78350f !important;
    }
    html.dark #card-threat-gauge.card-threat-tier-gold #lbl-instant-threat { color: #fcd34d !important; }
    :root #card-threat-gauge.card-threat-tier-gold #lbl-instant-threat { color: #92400e !important; }
    html.dark #card-threat-gauge.card-threat-tier-gold #lbl-wbgt-method,
    html.dark #card-threat-gauge.card-threat-tier-gold #lbl-thermal-debt,
    html.dark #card-threat-gauge.card-threat-tier-gold #lbl-cardiac-reset { color: #fde68a !important; }
    :root #card-threat-gauge.card-threat-tier-gold #lbl-wbgt-method,
    :root #card-threat-gauge.card-threat-tier-gold #lbl-thermal-debt,
    :root #card-threat-gauge.card-threat-tier-gold #lbl-cardiac-reset { color: #b45309 !important; }
    :root #card-threat-gauge.card-threat-tier-gold #btn-what-should-i-do {
      background-color: #78350f !important;
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-gold #btn-why-risk-critical {
      background-color: rgba(255, 255, 255, 0.9) !important;
      color: #78350f !important;
      border-color: rgba(245, 158, 11, 0.45) !important;
    }
    :root #card-threat-gauge.card-threat-tier-gold #gauge-track-circle {
      stroke: rgba(253, 230, 138, 0.7) !important;
    }

    /* TIER 3: ORANGE SHADE (51% - 79% Thermal Debt, Severe Stress) */
    html.dark #card-threat-gauge.card-threat-tier-orange {
      background: linear-gradient(135deg, #7c2d12 0%, #541c09 40%, #200d06 80%, #0b131e 100%) !important;
      border: 1px solid rgba(249, 115, 22, 0.55) !important;
      box-shadow: 0 12px 38px -5px rgba(234, 88, 12, 0.45), 0 0 25px rgba(249, 115, 22, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.18) !important;
    }
    :root #card-threat-gauge.card-threat-tier-orange {
      background: linear-gradient(135deg, #ffedd5 0%, #fed7aa 35%, #fff7ed 70%, #ffffff 100%) !important;
      border: 1px solid rgba(249, 115, 22, 0.45) !important;
      box-shadow: 0 10px 32px -4px rgba(249, 115, 22, 0.22), 0 4px 16px rgba(0, 0, 0, 0.05) !important;
    }
    html.dark #card-threat-gauge.card-threat-tier-orange #hero-temp-feels,
    html.dark #card-threat-gauge.card-threat-tier-orange #lbl-feels-like,
    html.dark #card-threat-gauge.card-threat-tier-orange #txt-thermal-debt-pct {
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-orange #hero-temp-feels,
    :root #card-threat-gauge.card-threat-tier-orange #lbl-feels-like,
    :root #card-threat-gauge.card-threat-tier-orange #txt-thermal-debt-pct {
      color: #7c2d12 !important;
    }
    html.dark #card-threat-gauge.card-threat-tier-orange #lbl-instant-threat { color: #fdba74 !important; }
    :root #card-threat-gauge.card-threat-tier-orange #lbl-instant-threat { color: #9a3412 !important; }
    html.dark #card-threat-gauge.card-threat-tier-orange #lbl-wbgt-method,
    html.dark #card-threat-gauge.card-threat-tier-orange #lbl-thermal-debt,
    html.dark #card-threat-gauge.card-threat-tier-orange #lbl-cardiac-reset { color: #fed7aa !important; }
    :root #card-threat-gauge.card-threat-tier-orange #lbl-wbgt-method,
    :root #card-threat-gauge.card-threat-tier-orange #lbl-thermal-debt,
    :root #card-threat-gauge.card-threat-tier-orange #lbl-cardiac-reset { color: #c2410c !important; }
    :root #card-threat-gauge.card-threat-tier-orange #btn-what-should-i-do {
      background-color: #7c2d12 !important;
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-orange #btn-why-risk-critical {
      background-color: rgba(255, 255, 255, 0.9) !important;
      color: #7c2d12 !important;
      border-color: rgba(249, 115, 22, 0.45) !important;
    }
    :root #card-threat-gauge.card-threat-tier-orange #gauge-track-circle {
      stroke: rgba(254, 215, 170, 0.7) !important;
    }

    /* TIER 4: RED SHADE (80% - 100% Thermal Debt, Critical Emergency) */
    html.dark #card-threat-gauge.card-threat-tier-red,
    html.dark #card-threat-gauge:not([class*="card-threat-tier-"]) {
      background: linear-gradient(135deg, #7f1d1d 0%, #5c0f1e 40%, #1e1122 80%, #0b131e 100%) !important;
      border: 1px solid rgba(255, 69, 105, 0.55) !important;
      box-shadow: 0 12px 38px -5px rgba(185, 28, 28, 0.45), 0 0 25px rgba(255, 45, 85, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.18) !important;
    }
    :root #card-threat-gauge.card-threat-tier-red,
    :root #card-threat-gauge:not([class*="card-threat-tier-"]) {
      background: linear-gradient(135deg, #fee2e2 0%, #fecaca 35%, #fff1f2 70%, #ffffff 100%) !important;
      border: 1px solid rgba(239, 68, 68, 0.45) !important;
      box-shadow: 0 10px 32px -4px rgba(220, 38, 38, 0.20), 0 4px 16px rgba(0, 0, 0, 0.05) !important;
    }
    html.dark #card-threat-gauge.card-threat-tier-red #hero-temp-feels,
    html.dark #card-threat-gauge.card-threat-tier-red #lbl-feels-like,
    html.dark #card-threat-gauge.card-threat-tier-red #txt-thermal-debt-pct {
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-red #hero-temp-feels,
    :root #card-threat-gauge.card-threat-tier-red #lbl-feels-like,
    :root #card-threat-gauge.card-threat-tier-red #txt-thermal-debt-pct {
      color: #881337 !important;
    }
    html.dark #card-threat-gauge.card-threat-tier-red #lbl-instant-threat { color: #ff859d !important; }
    :root #card-threat-gauge.card-threat-tier-red #lbl-instant-threat { color: #9f1239 !important; }
    html.dark #card-threat-gauge.card-threat-tier-red #lbl-wbgt-method,
    html.dark #card-threat-gauge.card-threat-tier-red #lbl-thermal-debt,
    html.dark #card-threat-gauge.card-threat-tier-red #lbl-cardiac-reset { color: #fecdd3 !important; }
    :root #card-threat-gauge.card-threat-tier-red #lbl-wbgt-method,
    :root #card-threat-gauge.card-threat-tier-red #lbl-thermal-debt,
    :root #card-threat-gauge.card-threat-tier-red #lbl-cardiac-reset { color: #9f1239 !important; }
    :root #card-threat-gauge.card-threat-tier-red #btn-what-should-i-do {
      background-color: #0f172a !important;
      color: #ffffff !important;
    }
    :root #card-threat-gauge.card-threat-tier-red #btn-why-risk-critical {
      background-color: rgba(255, 255, 255, 0.9) !important;
      color: #881337 !important;
      border-color: rgba(239, 68, 68, 0.4) !important;
    }
    :root #card-threat-gauge.card-threat-tier-red #gauge-track-circle {
      stroke: rgba(254, 202, 202, 0.8) !important;
    }
"""

# Replace the previous card-threat CSS with the dynamic tier CSS
if "DYNAMIC THERMAL DEBT TIER GRADIENTS" not in content:
    content = content.replace("/* Left Card Heat Aura Breathing Animation", tier_css + "\n    /* Left Card Heat Aura Breathing Animation")

# 2. Add JavaScript function applyThermalDebtColor(debtPct) and enhance switchWard and openDiagnosisModal
js_enhancements = """
    // --- Dynamic Thermal Debt Gradient Controller (0-10% Green -> 80-100% Red) --
    function applyThermalDebtColor(debtPct, customFeelsLike) {
      state.thermalDebt = Number(debtPct);
      const card = document.getElementById('card-threat-gauge');
      const ring = document.getElementById('radial-gauge-debt');
      const txtPct = document.getElementById('txt-thermal-debt-pct');
      const alertBadge = document.getElementById('hero-alert-badge');
      const cardiacReset = document.getElementById('lbl-cardiac-reset');
      const feelsLikeEl = document.getElementById('hero-temp-feels');
      const isHi = state.language === 'hi';

      if (!card) return;

      // Clean old tier classes
      card.classList.remove('card-threat-tier-green', 'card-threat-tier-gold', 'card-threat-tier-orange', 'card-threat-tier-red');

      let strokeColor = '#FF2D55';
      let badgeText = isHi ? 'लेवल 4 · उच्च जोखिम' : 'LEVEL 4 · HIGH RISK';
      let resetText = isHi ? 'कार्डियक रिकवरी नहीं' : 'NO CARDIAC RESET';

      if (debtPct <= 25) {
        // 0% - 25% GREEN SHADE (Specifically 0-10% green)
        card.classList.add('card-threat-tier-green');
        strokeColor = '#10B981';
        badgeText = isHi ? 'लेवल 1 · सुरक्षित / सामान्य' : 'LEVEL 1 · SAFE / NOMINAL';
        resetText = isHi ? 'पूर्ण कार्डियक रिकवरी' : 'FULL NOCTURNAL RESET';
      } else if (debtPct <= 50) {
        // 26% - 50% GOLD SHADE
        card.classList.add('card-threat-tier-gold');
        strokeColor = '#F59E0B';
        badgeText = isHi ? 'लेवल 2 · मध्यम सतर्कता' : 'LEVEL 2 · WATCH / MODERATE';
        resetText = isHi ? 'आंशिक कार्डियक रिकवरी' : 'MODERATE RECOVERY';
      } else if (debtPct <= 79) {
        // 51% - 79% ORANGE SHADE
        card.classList.add('card-threat-tier-orange');
        strokeColor = '#F97316';
        badgeText = isHi ? 'लेवल 3 · गंभीर तनाव' : 'LEVEL 3 · SEVERE STRESS';
        resetText = isHi ? 'अधूरी कार्डियक रिकवरी' : 'PARTIAL CARDIAC RESET';
      } else {
        // 80% - 100% RED SHADE
        card.classList.add('card-threat-tier-red');
        strokeColor = '#FF2D55';
        badgeText = isHi ? 'लेवल 4 · उच्च जोखिम' : 'LEVEL 4 · HIGH RISK';
        resetText = isHi ? 'कार्डियक रिकवरी नहीं' : 'NO CARDIAC RESET';
      }

      if (txtPct) txtPct.textContent = `${Math.round(debtPct)}%`;
      if (feelsLikeEl && customFeelsLike) feelsLikeEl.textContent = customFeelsLike;
      if (ring) {
        ring.setAttribute('stroke', strokeColor);
        const circumference = 301.6;
        const offset = circumference * (1 - (debtPct / 100));
        ring.style.strokeDashoffset = Math.max(0, offset);
      }
      if (alertBadge) alertBadge.textContent = badgeText;
      if (cardiacReset) cardiacReset.textContent = resetText;
    }
"""

if "applyThermalDebtColor" not in content:
    content = content.replace("// --- Ward Switcher Controller", js_enhancements + "\n    // --- Ward Switcher Controller")

# 3. Update switchWard to set telemetry and applyThermalDebtColor
old_switch = """      const wDict = wardNames[state.language] || wardNames.en;
      const overlayTitle = document.getElementById('overlay-ward-name');
      if (overlayTitle) overlayTitle.textContent = wDict[wardId] || wardId;

      const badgeWard = document.getElementById('badge-selected-ward-title');
      if (badgeWard) badgeWard.textContent = (wDict[wardId] || wardId) + (state.language === 'hi' ? ' / एपीआई लिंक' : ' / API LINKED');"""

new_switch = """      const wDict = wardNames[state.language] || wardNames.en;
      const overlayTitle = document.getElementById('overlay-ward-name');
      if (overlayTitle) overlayTitle.textContent = wDict[wardId] || wardId;

      const badgeWard = document.getElementById('badge-selected-ward-title');
      if (badgeWard) badgeWard.textContent = (wDict[wardId] || wardId) + (state.language === 'hi' ? ' / एपीआई लिंक' : ' / API LINKED');

      // Ward-Specific Thermal Debt & Telemetry Profiles
      const wardTelemetry = {
        'WARD-12': { feels: '48°', debt: 96, air: '41°C / 48°C', access: 'Deficit · 34% exposed', hydration: '3.5L / day', curfew: '11:30 – 4:30', haven: '450m away' },
        'WARD-15': { feels: '44°', debt: 68, air: '38°C / 44°C', access: 'Deficit · 22% exposed', hydration: '3.0L / day', curfew: '12:00 – 4:00', haven: '600m away' },
        'WARD-22': { feels: '41°', debt: 42, air: '36°C / 41°C', access: 'Moderate · 14% exposed', hydration: '2.5L / day', curfew: '12:30 – 3:30', haven: '350m away' },
        'WARD-08': { feels: '33°', debt: 8, air: '31°C / 33°C', access: 'Optimal · Safe zone', hydration: '2.0L / day', curfew: 'None', haven: '200m away' }
      };

      const telem = wardTelemetry[wardId] || wardTelemetry['WARD-12'];
      applyThermalDebtColor(telem.debt, telem.feels);

      const overlayTemps = document.getElementById('overlay-ward-temps');
      if (overlayTemps) overlayTemps.textContent = telem.air;
      const overlayAccess = document.getElementById('overlay-access-val');
      if (overlayAccess) overlayAccess.textContent = telem.access;

      const miniHydration = document.getElementById('hero-mini-hydration');
      if (miniHydration) miniHydration.textContent = telem.hydration;
      const miniCurfew = document.getElementById('hero-mini-curfew');
      if (miniCurfew) miniCurfew.textContent = telem.curfew;
      const miniHaven = document.getElementById('hero-mini-haven');
      if (miniHaven) miniHaven.textContent = telem.haven;"""

if old_switch in content:
    content = content.replace(old_switch, new_switch)

# 4. Enhance openDiagnosisModal to include interactive Thermal Debt Simulator Slider & Preset Buttons
old_modal = """            <p>• <strong>${isHi ? 'रात्रि रिकवरी का अभाव' : 'Nocturnal Deficit'}</strong>: ${isHi ? 'लगातार 3 रातों से न्यूनतम तापमान 28°C से ऊपर रहा, जिससे हृदय को आराम नहीं मिल सका।' : 'Night temperature remained >28°C for 3 consecutive nights, denying cellular recovery.'}</p>
          </div>
        `"""

new_modal = """            <p>• <strong>${isHi ? 'रात्रि रिकवरी का अभाव' : 'Nocturnal Deficit'}</strong>: ${isHi ? 'लगातार 3 रातों से न्यूनतम तापमान 28°C से ऊपर रहा, जिससे हृदय को आराम नहीं मिल सका।' : 'Night temperature remained >28°C for 3 consecutive nights, denying cellular recovery.'}</p>
            
            <!-- Live Thermal Debt & Gradient Simulator -->
            <div class="mt-4 pt-4 border-t k-border space-y-3">
              <div class="flex items-center justify-between">
                <span class="font-bold text-xs k-text-main">${isHi ? 'थर्मल डेब्ट कलर टेस्ट सिम्युलेटर' : 'Live Thermal Debt Gradient Simulator'}:</span>
                <span id="modal-live-debt-val" class="px-2 py-0.5 rounded font-mono font-bold text-xs bg-slate-500/20 text-[#00E5FF]">${state.thermalDebt || 96}%</span>
              </div>
              <input type="range" min="0" max="100" value="${state.thermalDebt || 96}" class="w-full h-2 rounded-lg cursor-pointer accent-[#FF2D55]" oninput="document.getElementById('modal-live-debt-val').textContent = this.value + '%'; applyThermalDebtColor(this.value);" />
              <div class="flex justify-between text-[10px] font-mono k-text-muted">
                <span class="text-[#10B981] font-bold">0-10% GREEN</span>
                <span class="text-[#F59E0B] font-bold">26-50% GOLD</span>
                <span class="text-[#F97316] font-bold">51-79% ORANGE</span>
                <span class="text-[#FF2D55] font-bold">80-100% RED</span>
              </div>
              <div class="grid grid-cols-4 gap-1.5 pt-1">
                <button onclick="applyThermalDebtColor(8); document.getElementById('modal-live-debt-val').textContent = '8%';" class="py-1 px-1 rounded-lg bg-[#064E3B] text-[#A7F3D0] border border-[#10B981]/40 text-[10px] font-mono font-bold hover:brightness-110 cursor-pointer">8% Green</button>
                <button onclick="applyThermalDebtColor(42); document.getElementById('modal-live-debt-val').textContent = '42%';" class="py-1 px-1 rounded-lg bg-[#78350F] text-[#FDE68A] border border-[#F59E0B]/40 text-[10px] font-mono font-bold hover:brightness-110 cursor-pointer">42% Gold</button>
                <button onclick="applyThermalDebtColor(68); document.getElementById('modal-live-debt-val').textContent = '68%';" class="py-1 px-1 rounded-lg bg-[#7C2D12] text-[#FED7AA] border border-[#F97316]/40 text-[10px] font-mono font-bold hover:brightness-110 cursor-pointer">68% Orange</button>
                <button onclick="applyThermalDebtColor(96); document.getElementById('modal-live-debt-val').textContent = '96%';" class="py-1 px-1 rounded-lg bg-[#7F1D1D] text-[#FECDD3] border border-[#FF2D55]/40 text-[10px] font-mono font-bold hover:brightness-110 cursor-pointer">96% Red</button>
              </div>
            </div>
          </div>
        `"""

if old_modal in content:
    content = content.replace(old_modal, new_modal)

# 5. Initialize default thermal debt on mount
if "applyThermalDebtColor(96)" not in content:
    content = content.replace("renderGuidanceTiles();\n      }", "renderGuidanceTiles();\n        applyThermalDebtColor(96);\n      }")

with open("frontend/index.html", "w", encoding="utf-8") as f:
    f.write(content)

with open("frontend/index_enhanced.html", "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: Dynamic thermal debt color tiers applied successfully!")
print("card-threat-tier-green in index.html:", "card-threat-tier-green" in content)
print("applyThermalDebtColor in index.html:", "applyThermalDebtColor" in content)
print("modal-live-debt-val in index.html:", "modal-live-debt-val" in content)
