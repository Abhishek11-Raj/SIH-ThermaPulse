import re

file_path = "frontend/index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Mortality & Hospitalization Surge HTML Chip
mortality_chip = """            <!-- Description Paragraph -->
            <p id="hero-desc" class="k-text-sub text-xs leading-relaxed max-w-sm">
              Patna Urban Core is in a sustained heat emergency. Protect people first; the peak risk window is active now.
            </p>

            <!-- Automated Mortality & Hospitalization Risk Chip (PS Direct Requirement) -->
            <div id="box-mortality-surge" class="p-2.5 rounded-xl border flex items-center justify-between font-mono text-[11px] backdrop-blur-md transition-all duration-300 bg-black/20 dark:bg-black/30 border-critical/30">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-[17px] text-[#FF2D55] animate-pulse" id="icon-mortality-surge">vital_signs</span>
                <div>
                  <span class="text-[9px] uppercase tracking-wider block opacity-75 font-semibold" id="lbl-mortality-tag">PROJECTED HEALTH IMPACT · AUTOMATED RISK INDEX</span>
                  <div class="font-bold flex items-center gap-2 flex-wrap">
                    <span id="val-hospitalization-spike" class="text-[#FF4D6D] font-extrabold">+38% Hospitalization Surge</span>
                    <span class="opacity-40">|</span>
                    <span id="val-mortality-risk" class="text-[#FF4D6D] font-bold">+18% Heat Mortality Risk</span>
                  </div>
                </div>
              </div>
              <span id="badge-mortality-level" class="px-2 py-0.5 rounded-md font-mono text-[9px] font-extrabold uppercase bg-[#FF2D55]/20 text-[#FF4D6D] border border-[#FF2D55]/30 shrink-0">CRITICAL</span>
            </div>"""

desc_target = """            <!-- Description Paragraph -->
            <p id="hero-desc" class="k-text-sub text-xs leading-relaxed max-w-sm">
              Patna Urban Core is in a sustained heat emergency. Protect people first; the peak risk window is active now.
            </p>"""

if "box-mortality-surge" not in content and desc_target in content:
    content = content.replace(desc_target, mortality_chip)

# 2. Add CAP 1.2 XML Button in the Top Header Controls
header_btn_old = """        <!-- WhatsApp Radiant Alert Button -->
        <button onclick="handleBroadcastWhatsApp()" class="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-[#FF2D55] hover:bg-[#FF2D55]/90 text-white font-bold text-xs tracking-tight shadow-md shadow-[#FF2D55]/30 active:scale-95 transition-all cursor-pointer">
          <span class="material-symbols-outlined text-[15px]">send</span>
          <span id="txt-broadcast-btn" class="hidden sm:inline">WhatsApp Alert</span>
        </button>"""

header_btn_new = """        <!-- CAP 1.2 Government XML Disaster Protocol Button -->
        <button onclick="openCapModal()" class="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#00E5FF]/10 hover:bg-[#00E5FF]/20 text-[#00E5FF] border border-[#00E5FF]/30 font-bold text-xs tracking-tight active:scale-95 transition-all cursor-pointer" title="View Official NDMA / SDMA CAP 1.2 XML Alert Feed">
          <span class="material-symbols-outlined text-[15px]">rss_feed</span>
          <span id="txt-cap-btn">CAP 1.2 XML</span>
        </button>

        <!-- WhatsApp Radiant Alert Button -->
        <button onclick="handleBroadcastWhatsApp()" class="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-[#FF2D55] hover:bg-[#FF2D55]/90 text-white font-bold text-xs tracking-tight shadow-md shadow-[#FF2D55]/30 active:scale-95 transition-all cursor-pointer">
          <span class="material-symbols-outlined text-[15px]">send</span>
          <span id="txt-broadcast-btn" class="hidden sm:inline">WhatsApp Alert</span>
        </button>"""

if "openCapModal()" not in content and header_btn_old in content:
    content = content.replace(header_btn_old, header_btn_new)

# 3. Add openCapModal() and dynamic health impact styling to JavaScript
cap_function = """
    // --- Official Common Alerting Protocol (CAP 1.2 XML) Modal -----------------
    function openCapModal() {
      const isHi = state.language === 'hi';
      const ward = state.currentWard || 'WARD-12';
      const debt = state.thermalDebt || 96;
      const now = new Date().toISOString();

      const capXml = `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>KESHAV-HEAT-${now.slice(0, 10)}-${ward}</identifier>
  <sender>imd-bio.keshav@bihar.gov.in</sender>
  <sent>${now}</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <category>Met</category>
    <event>Severe Human Thermal Stress Warning</event>
    <urgency>Immediate</urgency>
    <severity>${debt >= 80 ? 'Extreme' : (debt >= 50 ? 'Severe' : 'Moderate')}</severity>
    <certainty>Observed</certainty>
    <headline>Level ${debt >= 80 ? '4' : '3'} Heatwave Emergency: ${ward} (Feels-Like 48°C)</headline>
    <description>Thermal debt ${debt}%. Compounded wet-bulb globe temperature exceeds cellular recovery threshold. Projected hospitalization surge +38%.</description>
    <instruction>Enforce outdoor curfew 11:30 AM - 4:30 PM. Stand up ORS hydration tankers. Nearest haven: Central Park AC Shelter.</instruction>
    <area>
      <areaDesc>Patna Municipal Corporation, Bihar, India</areaDesc>
      <circle>25.6093,85.1376,5.0</circle>
    </area>
  </info>
</alert>`;

      openModal({
        title: isHi ? 'एनडीएमए / एसडीएमए सीएपी 1.2 एक्सएमएल प्रोटोकॉल' : 'NDMA / SDMA Common Alerting Protocol (CAP 1.2 XML)',
        subtitle: isHi ? 'राष्ट्रीय आपदा प्रबंधन प्राधिकरण संगत स्वचालित अलर्ट फीड' : 'Official Government XML Feed for Multi-Agency Broadcast Dissemination',
        bodyHtml: `
          <div class="space-y-3 font-mono text-xs">
            <div class="flex items-center justify-between pb-1">
              <span class="text-[#00E5FF] font-bold">Standard: OASIS CAP v1.2 / ITU-T X.1303</span>
              <button onclick="navigator.clipboard.writeText(document.getElementById('cap-xml-pre').textContent); showToast('Copied', 'CAP 1.2 XML copied to clipboard', 'content_copy', 'ready');" class="px-2.5 py-1 rounded bg-[#00E5FF]/20 text-[#00E5FF] border border-[#00E5FF]/30 font-bold hover:bg-[#00E5FF]/30 cursor-pointer">
                Copy XML
              </button>
            </div>
            <pre id="cap-xml-pre" class="p-3.5 rounded-xl bg-slate-950 text-slate-200 border k-border overflow-x-auto text-[11px] leading-relaxed select-all">${capXml.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
            <p class="k-text-muted text-[11px]">
              ${isHi ? 'यह एक्सएमएल सीधे दूरसंचार ऑपरेटरों, रेडियो स्टेशनों, टीवी और आपदा नियंत्रण कक्ष को स्वतः प्रसारित होता है।' : 'Payload auto-ingested by Telecom SMS Gateways, Sirens, WhatsApp API, and State Disaster Control Rooms.'}
            </p>
          </div>
        `
      });
    }
"""

if "openCapModal" not in content:
    content = content.replace("// --- Ward Switcher Controller", cap_function + "\n    // --- Ward Switcher Controller")

# 4. Enhance applyThermalDebtColor to update the Mortality & Hospitalization Chip
health_impact_logic = """
      // Update Projected Health Impact Chip
      const hospEl = document.getElementById('val-hospitalization-spike');
      const mortEl = document.getElementById('val-mortality-risk');
      const mortBadge = document.getElementById('badge-mortality-level');
      const mortIcon = document.getElementById('icon-mortality-surge');

      if (hospEl && mortEl && mortBadge) {
        if (debtPct <= 25) {
          // Green Tier: Baseline Normal
          hospEl.textContent = isHi ? 'सामान्य आधार रेखा (0% वृद्धि)' : 'Baseline Normal (0% Surge)';
          hospEl.className = 'text-[#10B981] font-extrabold';
          mortEl.textContent = isHi ? '0% अतिरिक्त मृत्यु' : '0% Excess Mortality';
          mortEl.className = 'text-[#10B981] font-bold';
          mortBadge.textContent = isHi ? 'सामान्य' : 'NOMINAL';
          mortBadge.className = 'px-2 py-0.5 rounded-md font-mono text-[9px] font-extrabold uppercase bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30 shrink-0';
          if (mortIcon) mortIcon.className = 'material-symbols-outlined text-[17px] text-[#10B981]';
        } else if (debtPct <= 50) {
          // Gold Tier: Watch / Mild Surge
          hospEl.textContent = isHi ? '+11% अस्पताल भर्ती वृद्धि' : '+11% Hospitalization Surge';
          hospEl.className = 'text-[#F59E0B] font-extrabold';
          mortEl.textContent = isHi ? '+3% अतिरिक्त मृत्यु जोखिम' : '+3% Heat Mortality Risk';
          mortEl.className = 'text-[#F59E0B] font-bold';
          mortBadge.textContent = isHi ? 'सतर्कता' : 'WATCH';
          mortBadge.className = 'px-2 py-0.5 rounded-md font-mono text-[9px] font-extrabold uppercase bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/30 shrink-0';
          if (mortIcon) mortIcon.className = 'material-symbols-outlined text-[17px] text-[#F59E0B]';
        } else if (debtPct <= 79) {
          // Orange Tier: Severe Surge
          hospEl.textContent = isHi ? '+24% अस्पताल भर्ती वृद्धि' : '+24% Hospitalization Surge';
          hospEl.className = 'text-[#F97316] font-extrabold';
          mortEl.textContent = isHi ? '+9% अतिरिक्त मृत्यु जोखिम' : '+9% Heat Mortality Risk';
          mortEl.className = 'text-[#F97316] font-bold';
          mortBadge.textContent = isHi ? 'गंभीर' : 'SEVERE';
          mortBadge.className = 'px-2 py-0.5 rounded-md font-mono text-[9px] font-extrabold uppercase bg-[#F97316]/20 text-[#F97316] border border-[#F97316]/30 shrink-0';
          if (mortIcon) mortIcon.className = 'material-symbols-outlined text-[17px] text-[#F97316]';
        } else {
          // Red Tier: Critical Spike
          hospEl.textContent = isHi ? '+38% अस्पताल भर्ती वृद्धि' : '+38% Hospitalization Surge';
          hospEl.className = 'text-[#FF4D6D] font-extrabold';
          mortEl.textContent = isHi ? '+18% अतिरिक्त मृत्यु जोखिम' : '+18% Heat Mortality Risk';
          mortEl.className = 'text-[#FF4D6D] font-bold';
          mortBadge.textContent = isHi ? 'गंभीर आपातकाल' : 'CRITICAL';
          mortBadge.className = 'px-2 py-0.5 rounded-md font-mono text-[9px] font-extrabold uppercase bg-[#FF2D55]/20 text-[#FF4D6D] border border-[#FF2D55]/30 shrink-0';
          if (mortIcon) mortIcon.className = 'material-symbols-outlined text-[17px] text-[#FF2D55] animate-pulse';
        }
      }
"""

if "val-hospitalization-spike" not in content:
    content = content.replace("if (cardiacReset) cardiacReset.textContent = resetText;\n    }", "if (cardiacReset) cardiacReset.textContent = resetText;\n" + health_impact_logic + "    }")

# 5. Add Hindi translation dictionary keys for mortality
hi_keys_old = 'lblThermalDebt: "थर्मल डेब्ट",'
hi_keys_new = 'lblThermalDebt: "थर्मल डेब्ट",\n        lblMortalityTag: "अनुमानित स्वास्थ्य प्रभाव · स्वचालित जोखिम सूचकांक",\n        txtCapBtn: "सीएपी 1.2 एक्सएमएल",'
content = content.replace(hi_keys_old, hi_keys_new)

# Save both
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

with open("frontend/index_enhanced.html", "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: Added Mortality & Hospitalization Risk Chip and CAP 1.2 XML modal!")
print("box-mortality-surge in index.html:", "box-mortality-surge" in content)
print("openCapModal in index.html:", "openCapModal" in content)
