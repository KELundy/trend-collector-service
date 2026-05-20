// ═══════════════════════════════════════════════════════════════════════════
// HomeBridge — app.js
// Clean rebuild. Same API contracts. Same localStorage keys. No patches.
// ═══════════════════════════════════════════════════════════════════════════

// ─────────────────────────────────────────────
// SECTION 1: CONFIG
// ─────────────────────────────────────────────
const BACKEND_URL = "https://api.homebridgegroup.co";

// ─────────────────────────────────────────────
// SECTION 1B: JORDAN — CHIEF OF STAFF SYSTEM
// ─────────────────────────────────────────────

// Jordan is the agent's Chief of Staff — the first mate they meet,
// the one who introduces the team, and the one always available when
// the agent needs help. Lives in localStorage under hb_jordan.
// Default name: Jordan. Agent can rename in Profile.

function jordanGet() {
  try { return JSON.parse(localStorage.getItem("hb_jordan") || "{}"); } catch(e) { return {}; }
}
function jordanSave(data) {
  localStorage.setItem("hb_jordan", JSON.stringify({ ...jordanGet(), ...data }));
}
function jordanName() {
  return jordanGet().name || "Jordan";
}
function jordanBrief() {
  return jordanGet().brief || "";
}
function jordanWelcomeDone() {
  return jordanGet().welcomeDone === true;
}
function jordanNamingDone() {
  return jordanGet().namingDone === true;
}

// Context-aware messages Jordan delivers per panel
// Add to this object as new panels and features are built
const JORDAN_MESSAGES = {
  "home-panel": {
    title: "Good to see you.",
    body: (name) => `Your Analyst has been watching your market. Any story that catches your eye is ready to become a post — just tap it and Your Writer takes over. This is your command center, ${name}.`
  },
  "content-engine-panel": {
    title: "Your Writer is ready.",
    body: () => `Pick a mode and Your Writer will shape your content in your voice. Generate a Post is the fastest start. Local Intel is the most powerful — try an address or neighborhood name.`
  },
  "setup-panel": {
    title: "This is your Focus panel.",
    body: () => `Focus tells Your Scheduler and Your Writer what to work on automatically. Your niches drive what gets generated. Your schedule drives when. Set it once — your team handles the rest.`
  },
  "profile-panel": {
    title: "Your profile shapes everything.",
    body: (name) => `Everything in your Profile — especially your Zone of Greatness — is what Your Writer uses to make content sound like you, not like AI. The more you give them, the better the output, ${name}. Don't skip the Zone of Greatness fields.`
  },
  "library-panel": {
    title: "Your content Records.",
    body: () => `Your Auditor has checked everything here before it arrived. Pending items are waiting for your approval — you're always the final decision-maker. Archive anything you don't need. Delete only from the Archive.`
  },
  "partner-panel": {
    title: "Your Partner Program.",
    body: () => `Share your referral link and earn up to 25% of every subscriber's revenue — every quarter they stay active. Your tier advances automatically. No applications needed.`
  },
  "getting-started-panel": {
    title: "Let's get you set up.",
    body: (name) => `I'll walk you through the essentials, ${name}. Once this is done, your team has everything they need to start working for you. It takes about five minutes.`
  }
};

function jordanMessageFor(panelTarget) {
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  const firstName = (user?.agent_name || "").split(" ")[0] || "there";
  const msg = JORDAN_MESSAGES[panelTarget];
  if (!msg) return null;
  return {
    title: msg.title,
    body: msg.body(firstName)
  };
}

// Show Jordan's slide-in panel with context-aware message
function openJordanPanel(panelTarget) {
  const panel = document.getElementById("jordan-panel");
  if (!panel) return;
  const name = jordanName();
  const msg = jordanMessageFor(panelTarget || _currentPanel || "home-panel");
  const titleEl = document.getElementById("jordan-msg-title");
  const bodyEl  = document.getElementById("jordan-msg-body");
  const nameEl  = document.getElementById("jordan-display-name");
  if (nameEl)  nameEl.textContent  = name;
  if (titleEl) titleEl.textContent = msg ? msg.title : "How can I help?";
  if (bodyEl)  bodyEl.textContent  = msg ? msg.body  : "I'm here whenever you need guidance. Just ask.";
  panel.classList.add("open");
  document.getElementById("jordan-backdrop")?.classList.add("open");
}

function closeJordanPanel() {
  document.getElementById("jordan-panel")?.classList.remove("open");
  document.getElementById("jordan-backdrop")?.classList.remove("open");
}

// Track current panel for Jordan context
let _currentPanel = "home-panel";

// Show the welcome modal — fires once on first login after naming
function showJordanWelcomeModal() {
  const modal = document.getElementById("jordan-welcome-modal");
  if (!modal) return;
  const name = jordanName();
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  const agentFirst = (user?.agent_name || "").split(" ")[0] || "there";
  const nameEl = modal.querySelector(".jwm-jordan-name");
  const greetEl = modal.querySelector(".jwm-greeting");
  if (nameEl)  nameEl.textContent  = name;
  if (greetEl) greetEl.textContent = `Hi ${agentFirst}, I'm ${name} — your Chief of Staff.`;
  modal.classList.add("open");
}

function closeJordanWelcomeModal() {
  const modal = document.getElementById("jordan-welcome-modal");
  if (modal) modal.classList.remove("open");
  jordanSave({ welcomeDone: true });
}

// Show the Jordan naming overlay — fires once before welcome modal on first login
function showJordanNamingScreen() {
  const overlay = document.getElementById("jordan-naming-overlay");
  if (!overlay) return;
  overlay.classList.add("open");
}

function closeJordanNamingScreen() {
  const overlay = document.getElementById("jordan-naming-overlay");
  if (overlay) overlay.classList.remove("open");
}

function jordanConfirmName() {
  const input = document.getElementById("jordan-name-input");
  const name = (input?.value || "").trim() || "Jordan";
  const briefInput = document.getElementById("jordan-brief-input");
  const brief = (briefInput?.value || "").trim();
  jordanSave({ name, brief, namingDone: true });
  closeJordanNamingScreen();
  setTimeout(() => showJordanWelcomeModal(), 300);
}

function jordanSelectSuggestedName(name) {
  const input = document.getElementById("jordan-name-input");
  if (input) {
    input.value = name;
    // Highlight active chip
    document.querySelectorAll(".jordan-name-chip").forEach(c => {
      c.classList.toggle("active", c.dataset.name === name);
    });
  }
}

// ─────────────────────────────────────────────
// SECTION 2: DEMO DATA — Brooke Callahan
// ─────────────────────────────────────────────
const DEMO_DATA = {
  agentName:    "Brooke Callahan",
  businessName: "Callahan Properties Group",
  brokerage:    "eXp Realty — Austin",
  market:       "Austin, TX",
  serviceAreas: ["South Congress","Domain District","Cedar Park","East Austin","78701"],
  shortBio:     "I help tech professionals relocating to Austin find their footing fast — the right neighborhood, the right commute, the right home. 200+ relocations completed across California, Seattle, and the Northeast.",
  brandVoice:   "Confident, direct, warm. Speaks tech fluently. Never uses jargon for its own sake.",
  wordsAvoid:   "hustle, grind, guaranteed",
  wordsPrefer:  "trusted, community, precision",
  designations: ["ABR","CRS"],
  mlsNames:     ["Austin Board of REALTORS"],
  languagePref: "english",
  disclaimer:   "Brooke Callahan is a licensed real estate agent in Texas | eXp Realty | Equal Housing Opportunity | License #TX-DEMO-7742",
  primaryNiches:       ["Residential Buying & Selling","Relocation"],
  audienceDescription: "Tech professionals relocating to Austin from the Bay Area, Seattle, and the Northeast",
  // Zone of Greatness — shapes every generated post
  originStory:          "I relocated to Austin myself in 2017 from San Francisco after my company's IPO. I spent four months making expensive mistakes in a market I didn't understand. That experience — and what it cost me — is why I do this.",
  signaturePerspective: "Most agents sell you on a neighborhood. I tell you which one you'll actually stay in three years after you move there. Those are very different conversations.",
  unfairAdvantage:      "I speak fluent tech — compensation packages, RSU timing, remote work tradeoffs. My clients aren't explaining their situation to me. I already know it.",
  notForClient:         "I'm not the right fit for agents who want someone to just show them listings. I work best with clients who want a strategic partner.",
  ctaType:  "calendar",
  ctaUrl:   "calendly.com/brookecallahan-atx",
  ctaLabel: "Book a 15-min Austin relocation call",
  platforms: [
    { id:"instagram", name:"Instagram",  handle:"@brookecallahan.atx" },
    { id:"linkedin",  name:"LinkedIn",   handle:"brookecallahanatx"   },
    { id:"facebook",  name:"Facebook",   handle:"brookecallahanproperties" },
  ],
  score: 74,
  // Demo local signals — shown on Home dashboard
  signals: [
    {
      id: "demo-sig-1",
      area: "East Austin",
      headline: "259-unit mixed-use development approved at 6th & Onion — breaks ground Q3 2026",
      summary: "Austin Planning Commission approved a 259-unit mixed-use project at East 6th and Onion Street. The development includes ground-floor retail and is expected to add significant rental supply to one of the city's most active corridors. Buyers watching East Austin should understand what this means for values in the next 18 months.",
      signal_type: "local:development",
      relevance_score: 0.92,
      source_url: "austintexas.gov/permits",
    },
    {
      id: "demo-sig-2",
      area: "South Congress",
      headline: "South Congress Avenue inventory dropped 31% in 30 days — lowest since 2022",
      summary: "Active listings along the South Congress corridor hit a 4-year low this month. Median days on market fell to 9 days. Buyers competing in this area need to move faster and with fewer contingencies than the Austin market broadly.",
      signal_type: "local:market",
      relevance_score: 0.88,
      source_url: "",
    },
    {
      id: "demo-sig-3",
      area: "Domain District",
      headline: "Second major tech campus announced for Domain North — 2,400 jobs expected",
      summary: "A Fortune 500 technology company announced a new Austin campus adjacent to the Domain, expected to bring 2,400 jobs over three years. Domain District and Cedar Park properties within commuting distance are already seeing increased inquiry volume.",
      signal_type: "local:news",
      relevance_score: 0.85,
      source_url: "",
    },
  ],
  library: [
    { id:"demo-1", status:"approved", cir_id:"CIR-2026-ATX-0142", niche:"Relocation", platform:"linkedin",
      content:{ headline:"Why Silicon Valley Engineers Keep Choosing South Congress Over Palo Alto",
        post:"Three years ago, I helped a senior engineer from Apple make the move from Cupertino to Austin. Last week she referred her fourth colleague to me.\n\nThe pattern I keep seeing: they come for the cost of living. They stay for the community.\n\nAustin's tech corridor isn't just cheaper — it's building something. The Domain, East 6th, the new Q2 campus. If you're evaluating a relocation from any major tech hub, I'd love to show you what the numbers actually look like.\n\nWhich Austin neighborhood has surprised you most — the one that looked great on paper but felt different in person? — Brooke Callahan | eXp Realty — Austin",
        cta:"Book a 15-min Austin relocation call: calendly.com/brookecallahan-atx", hashtags:"#AustinRealEstate #TechRelocation #Austin #ReloToAustin",
        script:"If you're a tech professional and you've been watching Austin from a distance — here's what I want you to know.", thumbnailIdea:"Split image: San Francisco fog left, Austin skyline right." },
      compliance:{ overallStatus:"compliant", overall_verdict:"pass", fairHousing:"pass", brokerageDisclosure:"pass", narStandards:"pass", notes:[] },
      saved_at:"2026-03-01T14:22:00", savedAt:"2026-03-01T14:22:00",
      approved_at:"2026-03-01T18:05:00", approvedAt:"2026-03-01T18:05:00" },
    { id:"demo-2", status:"approved", cir_id:"CIR-2026-ATX-0143", niche:"Residential Buying & Selling", platform:"instagram",
      content:{ headline:"The Rate Buydown Strategy Most Austin Buyers Still Haven't Heard Of",
        post:"Rates feel high. But here's what most buyers aren't asking for — and most agents aren't mentioning.\n\nSeller-paid rate buydowns.\n\nIn today's Austin market, motivated sellers are willing to buy your rate down 1–2 points at closing. On a $550K home, that's a difference of $400–600/month for the first two years.\n\nI've used this on four deals in the last 90 days. It changes the math in ways that the listing price alone doesn't show.\n\nAre you calculating your monthly payment based on today's rate — or what a buydown could actually look like? — Brooke Callahan | eXp Realty — Austin",
        cta:"Book a 15-min Austin relocation call: calendly.com/brookecallahan-atx", hashtags:"#AustinRealEstate #FirstTimeHomeBuyer #RateBuydown" },
      compliance:{ overallStatus:"review", overall_verdict:"review", fairHousing:"pass", brokerageDisclosure:"pass", narStandards:"warn", notes:["⚠ Soft flags noted — safe to approve, review notes below","NAR Article 12: Verify specific rate claims before publishing."] },
      saved_at:"2026-03-03T09:15:00", savedAt:"2026-03-03T09:15:00",
      approved_at:"2026-03-03T11:30:00", approvedAt:"2026-03-03T11:30:00" },
    { id:"demo-3", status:"pending", niche:"Relocation", platform:"linkedin",
      content:{ headline:"A 259-Unit Development Just Got Approved in East Austin — Here's What It Means for Buyers",
        post:"I walked East 6th Street last week and something felt different. More cranes. More fencing. More 'coming soon' signage.\n\nNow I know why.\n\nAustin Planning Commission just approved a 259-unit mixed-use development at 6th and Onion. Ground floor retail. Residential above. Breaking ground Q3 2026.\n\nFor buyers watching East Austin: new supply is coming. For sellers already there: the window before that supply hits is shorter than you think.\n\nAre you tracking the development pipeline in the Austin neighborhoods you're watching — or just the active listings? — Brooke Callahan | eXp Realty — Austin",
        cta:"Book a 15-min Austin relocation call: calendly.com/brookecallahan-atx", hashtags:"#AustinRealEstate #EastAustin #LocalIntel #AustinDevelopment",
        thumbnailIdea:"Street-level photo of East 6th construction activity with Austin skyline visible." },
      compliance:{ overall_verdict:"pass", fairHousing:"pass", brokerageDisclosure:"pass", narStandards:"pass", notes:["📍 Sources: Austin Planning Commission permit record, austintexas.gov"] },
      saved_at:"2026-04-09T08:00:00", savedAt:"2026-04-09T08:00:00" },
    { id:"demo-4", status:"published", cir_id:"CIR-2026-ATX-0138", niche:"Relocation", platform:"facebook",
      content:{ headline:"The Austin School District Question Every Tech Family Asks Me",
        post:"Moving with kids? Here's the question I get more than any other:\n\n'Which Austin suburbs have the best schools AND the fastest commute to the Domain?'\n\nI've done this math for 40+ families. Cedar Park and Round Rock consistently top the ratings — and the Domain commute via 183A runs 22 minutes in non-peak hours.\n\nThe families who regret their choice almost always made it based on Zillow school ratings without visiting. The ones who don't always visited twice.\n\nWhat's driving your neighborhood decision more — the schools or the commute? — Brooke Callahan | eXp Realty — Austin",
        cta:"Book a 15-min Austin relocation call: calendly.com/brookecallahan-atx", hashtags:"#AustinFamilies #AustinSuburbs #TechRelocation" },
      compliance:{ overall_verdict:"pass", notes:[] },
      saved_at:"2026-03-06T11:00:00", savedAt:"2026-03-06T11:00:00",
      approved_at:"2026-03-06T14:22:00", approvedAt:"2026-03-06T14:22:00",
      published_at:"2026-03-07T09:00:00", publishedAt:"2026-03-07T09:00:00" },
  ]
};

// ─────────────────────────────────────────────
// SECTION 3: NICHE DATA
// ─────────────────────────────────────────────
const NICHE_CATEGORIES = {
  "Location": [
    "Specific neighborhoods",
    "Suburbs & master-planned communities",
    "ZIP-code specialist",
    "City / regional expert",
    "Waterfront communities",
    "Mountain communities",
    "Urban high-rises",
    "Historic districts",
    "Gated communities",
    "Resort & vacation markets",
    "Rural & acreage markets",
  ],
  "Customer type": [
    "First-time homebuyers",
    "Move-up buyers",
    "Downsizers",
    "Luxury buyers & sellers",
    "Seniors / 55+",
    "Military families",
    "Relocation clients",
    "Second-home buyers",
    "Vacation-home buyers",
    "Work-from-home buyers",
    "Pet-focused buyers",
    "Families with special housing needs",
  ],
  "Property type": [
    "Single-family homes",
    "Condos & townhomes",
    "Multi-family residential",
    "Commercial retail",
    "Commercial office",
    "Commercial industrial",
    "Land & lots",
    "Agricultural land",
    "Farms & ranches",
    "Vineyard properties",
    "Waterfront properties",
    "Historic homes",
    "Eco-friendly / green homes",
    "Smart homes",
  ],
  "Transaction & situation": [
    "Buyer representation",
    "Seller representation",
    "Probate sales",
    "Divorce sales",
    "Foreclosure",
    "Pre-foreclosure",
    "REO / bank-owned",
    "Bankruptcy",
    "Estate sales",
    "1031 exchange clients",
    "Off-market / pocket listings",
    "Creative finance",
  ],
  "New construction": [
    "Builder representation",
    "Master-planned communities",
    "New subdivisions",
    "Gated new developments",
    "HOA communities",
    "Custom-home builds",
    "Spec homes",
    "Build-to-rent communities",
  ],
  "Investment": [
    "Buy-and-hold",
    "Fix & flip",
    "BRRRR",
    "Small multifamily (2–4 units)",
    "Apartment buildings (5+ units)",
    "Cash flow focused",
    "Appreciation focused",
    "Investor clients",
    "1031 exchange",
    "Opportunity zones",
  ],
  "Rental": [
    "Long-term rentals",
    "Short-term rentals",
    "Vacation rentals",
    "Airbnb-style rentals",
    "Student rentals",
    "Section 8 / affordable housing",
    "Rent-to-own",
    "Landlord representation",
    "Mid-term / corporate rentals",
    "Property management",
  ],
  "Specialty": [
    "Resort properties",
    "Timeshares",
    "Equine properties",
    "Farm & ranch specialty",
    "Mobile & manufactured homes",
    "Green & sustainable housing",
    "Smart-home specialty",
    "Multi-generational homes",
    "Data centers",
    "Medical office",
    "Hospitality",
    "Mixed-use commercial",
  ],
  "Distressed": [
    "Probate / inherited homes",
    "Divorce-related sales",
    "Foreclosure",
    "Pre-foreclosure",
    "REO / bank-owned",
    "Bankruptcy",
    "Burned-out landlords",
    "Estate sales",
    "Care-driven housing transitions",
    "Emergency relocation",
  ],
  "Demographic": [
    "Veterans & VA buyers",
    "Seniors & retirees",
    "LGBTQ+ friendly",
    "Teachers & essential workers",
    "Remote workers",
    "Multigenerational families",
    "Foreign nationals & expats",
    "High-net-worth / UHNW clients",
    "Empty nesters",
    "Young professionals",
    "Divorcing couples",
    "Adult children helping parents",
  ],
};

// B2B niches for HomeBridge marketing context — no categories needed, show all directly
const NICHE_CATEGORIES_B2B = {
  "HomeBridge": [
    "Broker & Office Management",
    "Agent Productivity & Technology",
    "Real Estate Compliance",
    "PropTech & Innovation",
    "Mortgage & Lending",
  ],
};

const NICHE_DATA = {
  // ── LOCATION ──
  "Specific neighborhoods":             ["Hyperlocal farming","Door-knocking expert","Neighborhood market reports"],
  "Suburbs & master-planned communities":["School district focus","HOA communities","New subdivisions"],
  "ZIP-code specialist":                ["Data-driven micro-market","Listing density focus","Off-market pipeline"],
  "City / regional expert":             ["Metro market authority","Cross-suburb coverage","Regional relocation"],
  "Waterfront communities":             ["Lakefront","Riverfront","Coastal / oceanfront","Dock & slip access"],
  "Mountain communities":               ["Ski-in / ski-out","Altitude properties","Mountain cabin specialist"],
  "Urban high-rises":                   ["Condo towers","Penthouse sales","Lock-and-leave lifestyle"],
  "Historic districts":                 ["Preservation buyers","Tax credit expertise","Architecture-minded clients"],
  "Gated communities":                  ["Security-focused buyers","Private amenities","Luxury gated estates"],
  "Resort & vacation markets":          ["Seasonal sellers","Fractional ownership","Second-home buyers"],
  "Rural & acreage markets":            ["Acreage buyers","Privacy seekers","Hobby farms","Off-grid living"],
  // ── CUSTOMER TYPE ──
  "First-time homebuyers":              ["FHA / low down payment","Down payment assistance","Education-focused guidance"],
  "Move-up buyers":                     ["Equity leverage","Contingent offers","Timing coordination"],
  "Downsizers":                         ["Right-sizing","55+ communities","Lifestyle simplification","Senior transitions"],
  "Luxury buyers & sellers":            ["Private marketing","Concierge service","Off-market listings","UHNW representation"],
  "Seniors / 55+":                      ["SRES certified","Aging-in-place","Senior move management","55+ communities"],
  "Military families":                  ["VA loans","PCS timing","Base-adjacent neighborhoods","SCRA aware"],
  "Relocation clients":                 ["Corporate relo packages","Remote coordination","Fast timelines"],
  "Second-home buyers":                 ["Vacation properties","Investment + enjoyment","Seasonal use"],
  "Vacation-home buyers":               ["Resort markets","Short-term rental potential","Lifestyle properties"],
  "Work-from-home buyers":              ["Home office must-haves","Suburban / rural shift","Connectivity needs"],
  "Pet-focused buyers":                 ["Yard requirements","Pet-friendly communities","Dog parks & trails"],
  "Families with special housing needs":["Accessibility features","Multi-generational layouts","ADA considerations"],
  // ── PROPERTY TYPE ──
  "Single-family homes":                ["Starter homes","Move-up homes","Estate homes","Investor rentals"],
  "Condos & townhomes":                 ["Urban living","Low-maintenance","First-time buyers","Lock-and-leave"],
  "Multi-family residential":           ["2–4 units","5+ units","Mixed-income","Owner-occupied"],
  "Commercial retail":                  ["Strip centers","Anchor tenants","Restaurant space","Pop-up retail"],
  "Commercial office":                  ["Traditional office","Medical office","Flex / coworking","Owner-user"],
  "Commercial industrial":              ["Warehouses","Distribution centers","Cold storage","Manufacturing"],
  "Land & lots":                        ["Infill lots","Buildable lots","Spec builder lots"],
  "Agricultural land":                  ["Farmland","Ranchland","Irrigated acreage","Crop land"],
  "Farms & ranches":                    ["Working ranch","Livestock operations","Hobby farm","Large acreage"],
  "Vineyard properties":                ["Wine country","Agricultural zoning","Tasting room potential"],
  "Waterfront properties":              ["Lakefront","Riverfront","Oceanfront","Dock access"],
  "Historic homes":                     ["Preservation buyers","Renovation clients","Tax credit buyers"],
  "Eco-friendly / green homes":         ["Solar","Energy-efficient","LEED certified","Sustainable materials"],
  "Smart homes":                        ["Home automation","Tech-forward buyers","Connected features"],
  // ── TRANSACTION & SITUATION ──
  "Buyer representation":               ["Offer strategy","Due diligence","Negotiation","Contingency management"],
  "Seller representation":              ["Pricing strategy","Staging","Marketing","Days-on-market reduction"],
  "Probate sales":                      ["Court confirmation","Heir coordination","Estate pricing","AS-IS sales"],
  "Divorce sales":                      ["Neutral representation","Court orders","Fast resolution","Discreet process"],
  "Foreclosure":                        ["Distressed pricing","AS-IS condition","Bank timelines"],
  "Pre-foreclosure":                    ["Loss mitigation","Seller outreach","Quick close"],
  "REO / bank-owned":                   ["Bank-owned process","AS-IS sales","Investor buyers"],
  "Bankruptcy":                         ["Court-approved sales","Trustee coordination","Distressed sellers"],
  "Estate sales":                       ["Heir coordination","Estate pricing","Sensitive timelines"],
  "1031 exchange clients":              ["DST options","Exchange timelines","Qualified intermediary coordination"],
  "Off-market / pocket listings":       ["Private sales","Referral-based","Pre-market buyers"],
  "Creative finance":                   ["Assumable loans","Seller financing","Subject-to","Wrap mortgages"],
  // ── NEW CONSTRUCTION ──
  "Builder representation":             ["Builder contracts","Construction timelines","Warranty process"],
  "Master-planned communities":         ["Amenity-rich","Community lifestyle","Phased development"],
  "New subdivisions":                   ["Lot selection","Pre-sale pricing","Phase releases"],
  "Gated new developments":             ["Private amenities","Security","Luxury new builds"],
  "HOA communities":                    ["HOA rules & fees","Community governance","Amenity buyers"],
  "Custom-home builds":                 ["Architect coordination","Land + build packages","Custom finishes"],
  "Spec homes":                         ["Move-in ready","Builder inventory","Quick close"],
  "Build-to-rent communities":          ["Investor clients","Institutional buyers","Rental yield focus"],
  // ── INVESTMENT ──
  "Buy-and-hold":                       ["Cash flow analysis","Long-term appreciation","Portfolio building"],
  "Fix & flip":                         ["ARV analysis","Contractor networks","Short-term hold"],
  "BRRRR":                              ["Refinance strategy","Forced appreciation","Portfolio scaling"],
  "Small multifamily (2–4 units)":      ["House hacking","Owner-occupied","FHA financing"],
  "Apartment buildings (5+ units)":     ["Cap rate analysis","Value-add","Student housing","Senior housing"],
  "Cash flow focused":                  ["Rental yield","Expense analysis","Market rent comps"],
  "Appreciation focused":               ["Growth markets","Equity play","Long-term hold"],
  "Investor clients":                   ["Portfolio review","Acquisition analysis","Disposition strategy"],
  "1031 exchange":                      ["Exchange timelines","Replacement property","DST options"],
  "Opportunity zones":                  ["Tax incentive","Qualified opportunity funds","Long-term hold"],
  // ── RENTAL ──
  "Long-term rentals":                  ["12-month leases","Tenant screening","Stable cash flow"],
  "Short-term rentals":                 ["Airbnb / VRBO","Occupancy optimization","Licensing compliance"],
  "Vacation rentals":                   ["Resort markets","Seasonal income","Rental yield"],
  "Airbnb-style rentals":               ["STR licensing","Furnishing strategy","Platform management"],
  "Student rentals":                    ["University proximity","Per-bedroom pricing","High turnover"],
  "Section 8 / affordable housing":     ["HUD vouchers","Income-restricted","Community impact"],
  "Rent-to-own":                        ["Lease-option","Path to ownership","Credit-challenged buyers"],
  "Landlord representation":            ["Tenant placement","Lease negotiation","Eviction support"],
  "Mid-term / corporate rentals":       ["Travel nurses","Corporate housing","30–90 day stays"],
  "Property management":                ["Full-service management","Maintenance coordination","Owner reporting"],
  // ── SPECIALTY ──
  "Resort properties":                  ["Ski resorts","Golf communities","Beach resorts","Fractional ownership"],
  "Timeshares":                         ["Exit consulting","Resale market","Developer sales"],
  "Equine properties":                  ["Horse facilities","Arena & barn","Pasture acreage","Riding trails"],
  "Farm & ranch specialty":             ["Agricultural zoning","Water rights","Working operations"],
  "Mobile & manufactured homes":        ["Park-owned land","Land-home packages","Affordable housing"],
  "Green & sustainable housing":        ["Net-zero homes","Solar communities","Green certifications"],
  "Smart-home specialty":               ["Home automation","EV charging","Tech integration"],
  "Multi-generational homes":           ["In-law suites","Dual living","Extended family buyers"],
  "Data centers":                       ["Colocation","Hyperscale campuses","Edge computing","Powered shells"],
  "Medical office":                     ["Healthcare practices","Dental offices","Behavioral health"],
  "Hospitality":                        ["Hotels","Resorts","Extended stay","Boutique properties"],
  "Mixed-use commercial":               ["Residential + retail","Office + retail","Live-work"],
  // ── DISTRESSED ──
  "Probate / inherited homes":          ["Heir coordination","Estate pricing","Court confirmation","AS-IS sales"],
  "Divorce-related sales":              ["Neutral process","Court orders","Fast resolution"],
  "Foreclosure":                        ["Bank timelines","AS-IS condition","Distressed pricing"],
  "Pre-foreclosure":                    ["Loss mitigation","Quick close","Seller outreach"],
  "REO / bank-owned":                   ["Bank-owned process","Investor buyers","Bulk REO"],
  "Bankruptcy":                         ["Trustee coordination","Court-approved sales","Distressed sellers"],
  "Burned-out landlords":               ["Exit strategy","AS-IS sale","Quick close","Portfolio disposition"],
  "Estate sales":                       ["Sensitive timelines","Multiple heirs","Personal property coordination"],
  "Care-driven housing transitions":    ["Senior moves","Medical event","Family-coordinated sale"],
  "Emergency relocation":               ["Fast timeline","Remote coordination","Corporate or personal crisis"],
  // ── DEMOGRAPHIC ──
  "Veterans & VA buyers":               ["VA loans","No down payment","Entitlement restoration","IRRRL refinance"],
  "Seniors & retirees":                 ["Fixed income buyers","Downsizing","SRES certified","55+ communities"],
  "LGBTQ+ friendly":                    ["Inclusive neighborhoods","Safe community focus","Affirming service"],
  "Teachers & essential workers":       ["Workforce housing programs","Down payment grants","Neighborhood proximity"],
  "Remote workers":                     ["Home office space","Suburban & rural shift","Connectivity requirements"],
  "Multigenerational families":         ["In-law suites","Dual kitchens","Multi-unit structures"],
  "Foreign nationals & expats":         ["FIRPTA","Cross-border transactions","Remote closing","Currency considerations"],
  "High-net-worth / UHNW clients":      ["Private marketing","Discretion","Off-market","Concierge service"],
  "Empty nesters":                      ["Right-sizing","Low maintenance","Travel-friendly","Lock-and-leave"],
  "Young professionals":                ["Urban living","Condo entry point","Career relocation"],
  "Divorcing couples":                  ["Neutral process","Joint sale coordination","Sensitive timelines"],
  "Adult children helping parents":     ["Senior transitions","Long-distance coordination","Care community placement"],
};

// ── Niche-aware situations map ──
// Every key maps to situations that are genuinely relevant to that niche.
// getNicheSituations() assembles a deduplicated list from the agent's saved niches.
const SITUATIONS_BY_NICHE = {
  "Residential Buying & Selling": [
    "Low inventory — buyers are losing multiple offers",
    "Prices just shifted in my market — what sellers need to know",
    "Interest rates changed — how it affects buyers right now",
    "Spring market is heating up — timing advice for sellers",
    "Fall market slowdown — opportunity for serious buyers",
    "A home sat on the market too long — what went wrong",
    "Buyers are waiving contingencies — when that's a mistake",
    "Days on market are rising — what that means for pricing",
    "New listings hit the market — how to move fast without overpaying",
    "Appraisal came in low — what happens next",
    "Seller concessions are back — how to use them strategically",
    "Local neighborhood just changed — impact on values",
  ],
  "First-Time Homebuyers": [
    "First-time buyer is scared to make an offer in this market",
    "Buyer thinks they can't afford to buy — let's check the math",
    "Down payment myths that are keeping renters from buying",
    "Rent vs. buy — the real comparison right now in this market",
    "First-time buyer lost three offers — what to do differently",
    "Credit score questions holding back a first-time buyer",
    "FHA vs conventional — which is right for my buyer",
    "Down payment assistance programs most buyers don't know about",
    "The inspection process — what first-time buyers need to understand",
    "Closing costs surprise — how to prepare buyers before they're shocked",
    "Interest rate anxiety — helping first-time buyers think long-term",
  ],
  "Move-Up Buyers": [
    "Should I sell first or buy first — the real answer right now",
    "Bridge loan vs. contingent offer — which makes sense today",
    "How much equity do I actually have — and what can it do",
    "Move-up buyer nervous about losing their low rate",
    "Timing the sale and the purchase — how to avoid a gap",
    "Neighborhood upgrade — when it's worth paying more per square foot",
    "Family outgrew their starter home — what the move-up market looks like",
    "School district change as the driver — how to evaluate the trade-off",
  ],
  "Luxury Real Estate": [
    "Luxury market is softening — opportunity for well-qualified buyers",
    "Off-market luxury listing just became available",
    "Pricing a luxury home correctly — the mistakes most agents make",
    "High-net-worth buyer wants discretion — how I handle that",
    "Luxury home sat on the market — what the price needs to do",
    "New luxury development changing the neighborhood comp landscape",
    "Lifestyle-driven relocation into the luxury segment",
    "Luxury staging ROI — what actually moves needle at this price point",
    "Trophy property — how to market something that defies comps",
  ],
  "Investment Analysis": [
    "Cap rates are compressing — where the math still works",
    "Interest rates changed — how it reshapes investment returns",
    "Cash flow vs. appreciation — which market are we in right now",
    "A deal that looked good on paper that I walked away from",
    "1031 exchange window closing — what investors need to move on",
    "Tax season — depreciation and what investors often miss",
    "Rent growth is slowing in my market — impact on buy-and-hold math",
    "Investor opportunity in a down market — how I think about it",
    "Portfolio builder asking which asset class makes sense right now",
  ],
  "Fix & Flip": [
    "ARV came in lower than expected — how I adjusted",
    "Contractor cost overrun — the contingency rule I live by",
    "Distressed property I passed on — and why",
    "After-repair value in today's market vs. six months ago",
    "The neighborhood that's flipping fast right now — and the one that isn't",
    "Permitting delays killing flip margins — what to watch for",
    "Flip vs. hold decision — how I think through it",
    "Finding deals when inventory is tight — where I'm looking",
  ],
  "Short-Term Rentals / Airbnb": [
    "New STR regulation just passed — what investors need to know",
    "Occupancy rates in my market — the honest numbers",
    "STR vs. long-term rental — the cash flow comparison right now",
    "A property I recommended against for STR — and why",
    "Seasonality in my STR market — how to underwrite it correctly",
    "Airbnb algorithm changed — impact on revenue projections",
    "HOA restrictions on STR — what to check before buying",
    "Furnishing cost and timeline — what buyers underestimate",
  ],
  "Long-Term Rentals (BRRRR)": [
    "BRRRR deal I just closed — how the numbers worked",
    "Refinance environment right now — how it affects BRRRR math",
    "Rent prices in my market — what landlords can actually charge",
    "Vacancy rates rising — how to protect cash flow",
    "Tenant screening — the mistakes new landlords make",
    "Property management cost vs. self-managing — real comparison",
    "Value-add property I found — the before and after numbers",
  ],
  "Relocation": [
    "Out-of-state buyer touring virtually — how I make it work",
    "Neighborhood orientation for someone moving from across the country",
    "Cost of living comparison — what relocating buyers always get wrong",
    "Corporate relocation timeline — how to work backward from the move date",
    "Temporary housing while the purchase closes — options I recommend",
    "Remote worker choosing this market — what they're prioritizing",
    "School district research for relocating families — my process",
    "First visit to a new city — how I structure the buyer tour",
  ],
  "Veterans & Military": [
    "VA loan benefit most veterans aren't using correctly",
    "PCS relocation incoming — the timeline that actually works",
    "VA appraisal vs. conventional — the differences that matter",
    "Veteran using entitlement a second time — how it works",
    "Military buyer competing against cash offers — the strategy",
    "VA funding fee — when it's waived and when it isn't",
    "BAH and what it actually covers in this market",
    "VA loan in a competitive offer situation — how I position it",
  ],
  "New Construction": [
    "Builder incentives right now — what's real and what's fluff",
    "New construction vs. resale — honest comparison in today's market",
    "Upgrade ROI — what adds value and what doesn't",
    "Builder contract review — the clauses buyers miss",
    "Construction delay — what buyers can and can't do",
    "Lot selection strategy — the mistakes I see buyers make",
    "New development changing the neighborhood — impact on existing homes",
    "Builder is offering rate buydowns — how to evaluate them",
  ],
  "Seniors & 55+ Communities": [
    "Rightsizing conversation — how I approach it with families",
    "55+ community options in this market — what's available and at what price",
    "Aging-in-place vs. moving — how to help families think through it",
    "Adult children managing a parent's home — the timeline conversation",
    "Equity harvest — what a senior homeowner actually has to work with",
    "Memory care transition — how real estate fits into the plan",
    "Estate sale timing — when to list and when to wait",
  ],
  "Empty Nesters & Downsizing": [
    "Empty nester ready to downsize — where the conversation starts",
    "Selling the family home — the emotional side nobody talks about",
    "Equity harvest at this stage of life — what's realistic",
    "Downsizing math — what they'll net and what they can buy",
    "Maintenance-free lifestyle — what that actually looks like in this market",
    "HOA community vs. single family — the trade-offs for this buyer",
  ],
  "Estate & Probate Sales": [
    "Executor trying to sell an inherited home — where to start",
    "As-is sale vs. light renovation — what makes sense for an estate",
    "Heir disagreement on pricing — how I navigate it",
    "Probate timeline — what families need to understand",
    "Title issues on inherited property — what slows things down",
    "Out-of-state heir managing a local sale — my process",
    "Hoarder home or deferred maintenance — how to price and sell it",
    "Trust sale vs. probate — the difference and why it matters",
  ],
  "Pre-Foreclosure & Hardship": [
    "Homeowner behind on payments — options before foreclosure",
    "Short sale vs. foreclosure — honest comparison for a distressed seller",
    "Loan modification timeline — what to tell a homeowner facing default",
    "Cash offer for a distressed property — how I evaluate it for the seller",
    "Equity in a hardship situation — can they sell and come out ahead",
    "Hardship seller timeline is tight — how I move fast without cutting corners",
  ],
  "Divorce & Separation": [
    "Divorcing couple disagreeing on whether to sell — how I stay neutral",
    "Buyout vs. sell — helping divorcing clients run the numbers",
    "Attorney referred a divorce listing — my process for keeping it clean",
    "Timing a divorce sale around school year or tax year",
    "Neutral valuation for a divorce proceeding — how I approach it",
  ],
  "Land & Development": [
    "Zoning change just approved — what it means for land values nearby",
    "Entitlement risk — what buyers of raw land need to understand",
    "Utility access on a land parcel — what to check before making an offer",
    "Subdivision potential — how I evaluate it for a buyer",
    "Land banking in my market — is it the right moment",
    "Builder looking for infill lots — what's available and what it costs",
  ],
  "Commercial Sales": [
    "Cap rate compression in local commercial market",
    "1031 exchange buyer moving from residential into commercial",
    "Business owner wants to buy their building — the conversation",
    "Commercial property sitting vacant — how I market it differently",
    "Office vs. retail vs. industrial — where value is shifting in my market",
  ],
  "Property Management": [
    "Landlord asking whether to self-manage or hire out",
    "Tenant turnover cost — what landlords underestimate",
    "Rent price in my market — where I'm seeing leases land",
    "Deferred maintenance on a rental — the compounding cost",
    "Out-of-state landlord — problems I see and how to solve them",
  ],
  "FSBO (For Sale By Owner)": [
    "FSBO that called me after 60 days — what went wrong",
    "What FSBOs don't know about pricing that costs them money",
    "FSBO negotiating directly with a buyer — where deals fall apart",
    "The disclosure liability most FSBOs don't think about",
    "FSBO asking if I can just bring buyers — how I handle it",
    "What a net sheet actually looks like for a FSBO vs. listed property",
  ],
  "Expired Listings": [
    "Listing expired — the conversation I have when I call",
    "Why a home didn't sell — the honest diagnosis",
    "Pricing strategy for a relisted property — what has to change",
    "Expired seller who interviewed three agents — what they're thinking",
    "Staging and condition — what the market was telling the seller",
    "Marketing failure vs. pricing failure — how to tell the difference",
  ],
  "Circle Prospecting & Geographic Farming": [
    "Just sold in your neighborhood — what it means for your value",
    "Three homes sold on this street in 90 days — the pattern I'm seeing",
    "New development approved nearby — impact on neighborhood values",
    "Local market update for [neighborhood] — the numbers right now",
    "I knocked 40 doors last weekend — here's what homeowners are asking",
    "Homeowner who's been thinking about selling for two years — what's holding them back",
  ],
  "Sphere of Influence & Database Reactivation": [
    "Checking in with past clients — what I'm seeing in the market",
    "Client from three years ago just called — what they wanted to know",
    "Referral from a past client — how I honor that trust",
    "Market shift that affects people who bought or sold with me in the last five years",
    "Annual check-in — what your home is worth right now",
    "Database reactivation — the message that actually gets a response",
  ],
};

// Universal situations that apply regardless of niche — always included as base
const SITUATIONS_UNIVERSAL = [
  "Local development or neighborhood change affecting values",
  "Interest rates just moved — what it means for buyers and sellers right now",
  "A mistake I see clients make in this market — and how to avoid it",
  "The question I get asked most often right now",
  "What the data in my market is actually saying this week",
  "A deal I walked a client away from — and why",
  "Something most agents won't tell you about this market",
];

// Assemble niche-aware situations from agent's selected niches
// Returns deduplicated list: niche-specific first, universal appended
function getNicheSituations(niches) {
  if (!niches || !niches.length) return SITUATIONS_UNIVERSAL;
  const seen = new Set();
  const result = [];
  niches.forEach(niche => {
    const nicheSits = SITUATIONS_BY_NICHE[niche] || [];
    nicheSits.forEach(s => { if (!seen.has(s)) { seen.add(s); result.push(s); } });
  });
  SITUATIONS_UNIVERSAL.forEach(s => { if (!seen.has(s)) { seen.add(s); result.push(s); } });
  return result;
}

// Legacy constant — kept so any direct SITUATIONS references still resolve
// Points to universal set as safe fallback
const SITUATIONS = SITUATIONS_UNIVERSAL;

// B2B situations — HomeBridge marketing to brokers and office managers
const SITUATIONS_B2B = [
  "Agents at my office aren't posting consistently",
  "A compliance issue arose from an agent\'s social post",
  "We\'re losing listings to agents with stronger online presence",
  "New agents joining — how do I get them visible fast?",
  "The Compass/Anywhere merger is reshaping broker competition",
  "AI content is flooding social — authenticity is now a differentiator",
  "Our office brand is invisible — agents post as individuals only",
  "Broker wants to reduce compliance risk from agent social media",
  "Recruiting agents who expect modern marketing tools",
  "Office needs consistent content without hiring a marketing team",
  "Agents are using AI tools with zero compliance checks",
  "Google and LinkedIn are rewarding authentic, verified content",
  "Independent brokerage competing against franchise brand recognition",
  "Building a team brand that survives agent turnover",
];

// B2B personas — who brokers/office managers are talking to or thinking about
const PERSONAS_B2B = [
  "Boutique broker with 5–15 agents",
  "Franchise office manager",
  "Independent broker-owner",
  "Team leader recruiting agents",
  "Compliance officer at a large brokerage",
  "Broker evaluating technology vendors",
  "Office manager tired of chasing agents to post",
  "Broker whose agents are losing business to more visible competitors",
];

// Niche-aware audience mapping — who the agent is writing FOR
// Keys match primaryNiches values from Setup
const NICHE_PERSONAS = {
  "Seniors & 55+ Communities":    ["Seniors planning to downsize", "Empty nesters ready to simplify", "Retirees relocating", "Adults 55+ exploring senior communities", "Couples whose kids have left home"],
  "Seniors & Downsizing":         ["Seniors planning to downsize", "Empty nesters ready to simplify", "Retirees relocating", "Adults 55+ exploring senior communities", "Couples whose kids have left home"],
  "Empty Nesters & Downsizing":   ["Empty nesters ready to simplify", "Seniors planning to downsize", "Couples whose kids have left home", "Retirees relocating"],
  "First-Time Homebuyers":        ["First-time buyers nervous about the process", "Renters ready to stop paying someone else's mortgage", "Young couples buying their first home", "Single professionals buying solo"],
  "First-Time Buyers":            ["First-time buyers nervous about the process", "Renters ready to stop paying someone else's mortgage", "Young couples buying their first home", "Single professionals buying solo"],
  "Move-Up Buyers":               ["Growing families needing more space", "Homeowners ready to upgrade", "Move-up buyers with equity to leverage", "Couples outgrowing their starter home"],
  "Residential Buying & Selling": ["Buyers navigating today's market", "Sellers deciding when to list", "Homeowners thinking about their next move", "Relocating families", "Out-of-state buyers"],
  "Luxury Real Estate":           ["High-net-worth buyers seeking discretion", "Luxury home sellers", "Buyers seeking trophy properties", "Executives relocating", "Second-home buyers"],
  "Investment Analysis":          ["Buy-and-hold investors", "First-time real estate investors", "Investors analyzing market conditions", "Portfolio builders", "Passive income seekers"],
  "Investors":                    ["Buy-and-hold investors", "First-time real estate investors", "Investors analyzing market conditions", "Portfolio builders", "Passive income seekers"],
  "Fix & Flip":                   ["Experienced flippers", "New investors exploring fix-and-flip", "Contractors looking to invest", "Value-add buyers"],
  "Short-Term Rentals / Airbnb":  ["Airbnb hosts", "Short-term rental investors", "Vacation property buyers", "Investors analyzing STR markets"],
  "Short-Term Rentals":           ["Airbnb hosts", "Short-term rental investors", "Vacation property buyers"],
  "Long-Term Rentals (BRRRR)":    ["Buy-and-hold landlords", "BRRRR strategy investors", "Passive income seekers", "Portfolio builders"],
  "1031 Exchange":                ["Investors doing a 1031 exchange", "Property owners deferring capital gains", "Portfolio rebalancers"],
  "Veterans & Military":          ["Active duty military relocating", "Veterans using VA loan benefits", "Military families on PCS orders", "Veterans buying their first home"],
  "Veterans":                     ["Active duty military relocating", "Veterans using VA loan benefits", "Military families on PCS orders"],
  "Relocation":                   ["Families relocating for work", "Out-of-state buyers", "Corporate transferees", "Remote workers choosing a new city"],
  "New Construction":             ["Buyers considering new construction", "Buyers comparing new vs. resale", "Move-up buyers wanting to customize"],
  "Luxury New Construction":      ["High-net-worth buyers building custom", "Luxury buyers wanting new finishes", "Buyers seeking smart home features"],
  "Second Homes & Vacation":      ["Second home buyers", "Vacation property investors", "Buyers seeking weekend retreats"],
  "Multi-Family (2-4 Units)":     ["House-hackers buying their first investment", "Small landlords", "Buyers wanting income to offset mortgage"],
  "Multi-Family (5+ Units)":      ["Apartment investors", "Commercial real estate investors", "Portfolio builders scaling up"],
  "Commercial Sales":             ["Business owners buying their space", "Commercial investors", "1031 exchange buyers moving into commercial"],
  "Commercial Leasing":           ["Business owners seeking space", "Tenants comparing lease options", "Companies expanding or downsizing"],
  "Mortgage & Lending":           ["Buyers confused about loan options", "Homeowners considering a refinance", "First-time buyers learning about financing"],
  "Divorce & Separation":         ["Divorcing couples navigating real estate", "Attorneys advising clients on property division"],
  "Probate & Inherited Homes":    ["Heirs managing inherited property", "Executors of estates", "Families navigating a difficult transition"],
  "Pre-Foreclosure & Hardship":   ["Homeowners facing financial difficulty", "Sellers needing to act quickly", "Distressed property owners"],
  "Property Management":          ["Landlords wanting hands-off management", "Out-of-state rental owners", "New landlords learning the business"],
  "Land & Development":           ["Developers seeking land", "Builders looking for lots", "Investors in raw land"],
  "Land & Rural":                 ["Rural property buyers", "Buyers seeking land and space", "Agricultural investors"],
  "Data Centers":                 ["Data center operators", "Institutional real estate investors", "Technology company real estate leads"],
};

// Fallback for niches with no specific mapping
const PERSONAS_GENERAL = [
  "Buyers navigating today's market",
  "Sellers deciding when to list",
  "Homeowners thinking about their next move",
  "First-time buyers",
  "Move-up buyers",
  "Investors",
  "Relocating families",
  "Out-of-state buyers",
];

// ─────────────────────────────────────────────
// SECTION 4: PLATFORM DATA
// ─────────────────────────────────────────────
const PLATFORM_META = [
  { id:"instagram", name:"Instagram",       types:["text","video"], icon:"📸" },
  { id:"tiktok",    name:"TikTok",          types:["video"],        icon:"🎵" },
  { id:"youtube",   name:"YouTube Shorts",  types:["video"],        icon:"▶️" },
  { id:"facebook",  name:"Facebook",        types:["text","video"], icon:"📘" },
  { id:"linkedin",  name:"LinkedIn",        types:["text","video"], icon:"💼" },
  { id:"twitter",   name:"X / Twitter",     types:["text","video"], icon:"𝕏"  },
  { id:"nextdoor",  name:"Nextdoor",        types:["text"],         icon:"🏘️" },
  { id:"reddit",    name:"Reddit",          types:["text","video"], icon:"🤖" },
];

function hashtagify(h) {
  return (h||"").split(/\s+/).filter(Boolean).map(t => t.startsWith("#") ? t : `#${t}`).join(" ");
}

const PLATFORMS = [
  { id:"linkedin",  label:"LinkedIn",          icon:"💼", hint:"Professional · Referral-friendly · Full length", status:"active",
    format:(c,id) => `${c.headline}\n\n${c.post}\n\n${c.cta}\n\n📍 ${id.name}${id.brokerage?` · ${id.brokerage}`:""} · ${id.market}${id.socials.linkedin?`\n🔗 ${id.socials.linkedin}`:""}\n\n${hashtagify(c.hashtags)}${id.disclaimer?`\n\n${id.disclaimer}`:""}${id.cirStamp?`\n${id.cirStamp}`:""}` },
  { id:"instagram", label:"Instagram",         icon:"📸", hint:"Visual-first · Punchy caption · Hashtag block",  status:"active",
    format:(c,id) => `${c.headline} 🏡\n\n${c.post}\n\n${c.cta}${id.socials.instagram?`\n\nFollow: ${id.socials.instagram}`:""}\n\n.\n.\n.\n${hashtagify(c.hashtags)} #realestate #realtor${id.disclaimer?`\n\n${id.disclaimer}`:""}${id.cirStamp?`\n${id.cirStamp}`:""}` },
  { id:"facebook",  label:"Facebook",          icon:"👥", hint:"Conversational · Community-focused · Longer form", status:"active",
    format:(c,id) => `${c.headline}\n\n${c.post}\n\n${c.cta}${id.socials.facebook?`\n\n👉 ${id.socials.facebook}`:""}\n\n— ${id.name}${id.brokerage?`, ${id.brokerage}`:""}\n📍 ${id.market}${id.disclaimer?`\n\n${id.disclaimer}`:""}${id.cirStamp?`\n${id.cirStamp}`:""}` },
  { id:"tiktok",    label:"TikTok",            icon:"🎵", hint:"Hook-first · Short · Trending tags",              status:"active",
    format:(c,id) => `${c.script?c.script.split(".")[0]+".":c.headline}\n\n${c.post.slice(0,180)}${c.post.length>180?"…":""}\n\n${hashtagify(c.hashtags)} #realestate #realtortok${id.socials.tiktok?`\n\n${id.socials.tiktok}`:""}${id.disclaimer?`\n\n${id.disclaimer}`:""}` },
  { id:"youtube",   label:"YouTube",           icon:"▶️", hint:"Title + Description + Tags · SEO-optimized",      status:"active",
    format:(c,id) => `TITLE:\n${c.headline}\n\nDESCRIPTION:\n${c.post}\n\n${c.cta}\n\n📍 ${id.name} serves ${id.market}.\n\nTAGS:\n${(c.hashtags||"").split(/\s+/).filter(Boolean).map(h=>h.replace("#","")).join(", ")}, real estate, ${id.market}${id.disclaimer?`\n\n${id.disclaimer}`:""}` },
  { id:"twitter",   label:"X / Twitter",       icon:"𝕏",  hint:"280 chars max · Hook-first",                      status:"active",
    format:(c,id) => `${c.headline}\n\n${c.post.slice(0,200)}${c.post.length>200?"…":""}\n\n#realestate #realtor${id.socials.twitter?` ${id.socials.twitter}`:""}` },
  { id:"threads",   label:"Threads",           icon:"🧵", hint:"Conversational · Growing fast",                   status:"active",
    format:(c,id) => `${c.headline}\n\n${c.post}\n\n${c.cta}${id.socials.threads?`\n\n${id.socials.threads}`:""}${id.disclaimer?`\n\n${id.disclaimer}`:""}` },
  { id:"reddit",    label:"Reddit",            icon:"🤖", hint:"Community-first · No hard sell · Value-driven",   status:"active",
    format:(c,id) => `**${c.headline}**\n\n${c.post}\n\n${c.cta}\n\nHappy to answer questions — ${id.name}, ${id.market}.${id.disclaimer?`\n\n${id.disclaimer}`:""}` },
  { id:"nextdoor",  label:"Nextdoor",          icon:"🏘️", hint:"Hyperlocal · Reaches your farm areas",            status:"active",
    format:(c,id) => `${c.headline}\n\n${c.post}\n\n${c.cta}\n\n📍 ${id.name}${id.brokerage?` · ${id.brokerage}`:""} · ${id.market}${id.disclaimer?`\n\n${id.disclaimer}`:""}${id.cirStamp?`\n${id.cirStamp}`:""}` },
  { id:"email",     label:"Email Newsletter",  icon:"✉️", hint:"Direct to inbox · No algorithm · Highest conversion", status:"active",
    format:(c,id) => `SUBJECT LINE:\n${c.headline}\n\n---\n\nHi [First Name],\n\n${c.post}\n\n${c.cta}\n\nBest,\n${id.name}${id.brokerage?`\n${id.brokerage}`:""}\n📍 ${id.market}${id.disclaimer?`\n\n${id.disclaimer}`:""}` },
];

// ─────────────────────────────────────────────
// SECTION 5: STATE
// ─────────────────────────────────────────────
let selectedPrimaryNiches  = [];
let selectedSubNiches      = [];
let activeNicheForGenerate = null;
let lastGeneratedContent   = {};
let _cachedLibrary         = null;
let _cachedLibraryContext  = null;  // Bug #8: track which context the cache belongs to
let reviewModalItemId      = null;
let currentLibraryFilter   = "all";
let libSelectedIds         = new Set(); // tracks checked row IDs for bulk actions
let activeDistributionItemId      = null;
let copiedPlatformsThisSession    = [];
let activeLibraryItemId           = null;
let activeCategoryFilter          = null;
let _schedules                    = {};
let _adminUsers                   = [];
let _adminPartners                = {};  // keyed by user_id — loaded alongside users
let _adminRoleFilter              = "all";
let filmStream   = null;
let filmRecorder = null;
let filmChunks   = [];
let filmSeconds  = 0;
let filmTimer    = null;
let autoScrollTimer = null;
let autoScrollActive = false;
let currentFacingMode = "user";
let currentFilmItem   = null;

// ─────────────────────────────────────────────
// SECTION 6: HELPERS
// ─────────────────────────────────────────────
function getSetupKey() {
  // Each context owns its own storage key
  try {
    const ctx = localStorage.getItem("hb_view_context");
    if (ctx === "marketing" || ctx === "hb_marketer") return "hb_hb_setup";
    if (ctx === "office")  return "hb_office_setup";
    if (ctx === "team")    return "hb_team_setup";
    return "hb_setup";
  } catch(e) { return "hb_setup"; }
}
function getSaved() { return JSON.parse(localStorage.getItem(getSetupKey()) || "{}"); }

// Returns the content context for API calls
// 'agent' = personal real estate content
// 'hb_marketing' = HomeBridge platform content
function getContentContext() {
  const ctx = getViewContext();
  if (ctx === "marketing" || ctx === "hb_marketing") return "hb_marketing";
  if (localStorage.getItem("hb_view_context") === "marketing") return "hb_marketing";
  return "agent";
}

// ── Context-aware setup save/get ──────────────────────────────────────────────
// All setup/save calls must go through _setupSave() and all setup/get calls
// through _setupGet(). In marketing context these route to the dedicated
// marketing-setup endpoints which write to users.hb_marketing_setup_json
// instead of agent_setup. This prevents any cross-contamination between
// Kevin's agent profile and the HomeBridge company profile.

function _isMarketingContext() {
  const ctx  = getViewContext();
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  return ctx === "marketing" || (user?.role === "hb_marketer");
}

async function _setupSave(setup) {
  if (_isMarketingContext()) {
    return authFetch(`${BACKEND_URL}/marketing-setup/save`, {
      method: "POST", body: JSON.stringify({ setup })
    }).catch(() => {});
  }
  return authFetch(`${BACKEND_URL}/setup/save`, {
    method: "POST", body: JSON.stringify({ setup })
  }).catch(() => {});
}

async function _setupGet() {
  if (_isMarketingContext()) {
    return authFetch(`${BACKEND_URL}/marketing-setup/get`);
  }
  return authFetch(`${BACKEND_URL}/setup/get`);
}
// ─────────────────────────────────────────────────────────────────────────────

function el(id)     { return document.getElementById(id); }
function set(id, v) { const e = el(id); if (e) e.textContent = v; }

function showMsg(id, msg, isError = false) {
  const e = el(id); if (!e) return;
  e.textContent = msg;
  e.style.display = msg ? "block" : "none";
  e.style.color = isError ? "var(--red,#b91c1c)" : "var(--green,#15803d)";
}
function hideMsg(id) { showMsg(id, ""); }

function getSocials() {
  const d = JSON.parse(localStorage.getItem("hb_socials") || "{}");
  return d.handles || d;
}
function getDisclaimer() {
  return localStorage.getItem("hb_disclaimer") || getSaved().disclaimer || "";
}
function getLanguagePref() {
  return localStorage.getItem("hb_lang") || "english";
}
function getDesignations() {
  const saved = getSaved();
  return Array.isArray(saved.designations) ? saved.designations : [];
}
function getServiceAreas() {
  return Array.isArray(getSaved().serviceAreas) ? getSaved().serviceAreas : [];
}
function getCustomNiches() {
  return JSON.parse(localStorage.getItem("hb_custom_niches") || "[]");
}
function getMarketContext() {
  const s = getSaved();
  const areas = getServiceAreas();
  if (s.market && areas.length) return `${s.market} (${areas.slice(0,3).join(", ")})`;
  return s.market || "";
}
function getActivePlatforms() {
  // Try DOM first (Profile panel is open); fall back to localStorage
  const fromDOM = PLATFORM_META.filter(p => {
    const e = el(`plat-active-${p.id}`);
    return e?.checked;
  });
  if (fromDOM.length) {
    return fromDOM.map(p => ({ ...p, handle: el(`social-${p.id}`)?.value?.trim() || "" }));
  }
  // DOM not live — read from saved setup
  const saved = getSaved();
  return Array.isArray(saved.platforms) ? saved.platforms : [];
}
function getContentDeliveryPrefs() {
  const active = getActivePlatforms();
  return { platforms: active.map(p=>p.name), activePlatforms: active };
}
function getInitials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return parts.length === 1 ? parts[0].slice(0,2).toUpperCase() : (parts[0][0]+parts[parts.length-1][0]).toUpperCase();
}

// ─────────────────────────────────────────────
// SECTION 7: AUTHENTICATED FETCH
// ─────────────────────────────────────────────
async function authFetch(url, options = {}) {
  const token    = localStorage.getItem("hb_token");
  const isDemo   = localStorage.getItem("hb_demo_mode") === "true";
  const isDemoTk = token === "demo-token";

  // Demo intercept — fake 200 for all non-generate endpoints
  if (isDemo && isDemoTk) {
    if (!url.includes("/content/generate-content")) {
      return new Response(JSON.stringify({ ok:true, items:[], schedules:[], users:[], total:0, score:67 }), {
        status: 200, headers: { "Content-Type":"application/json" }
      });
    }
    // Route to auth-free demo endpoint
    const demoUrl = url.replace("/content/generate-content", "/content/demo-generate");
    return fetch(demoUrl, { ...options, headers: { "Content-Type":"application/json", ...(options.headers||{}) } });
  }

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type":"application/json",
      ...(options.headers||{}),
      ...(token ? { "Authorization":`Bearer ${token}` } : {}),
    },
  });

  if (res.status === 401) {
    localStorage.removeItem("hb_token");
    localStorage.removeItem("hb_user");
    localStorage.removeItem("hb_view_context");
    localStorage.removeItem("hb_demo_mode");
    _cachedLibrary = null;
    window.location.href = "login.html";
    throw new Error("Session expired");
  }
  return res;
}

// ─────────────────────────────────────────────
// SECTION 8: LIBRARY API
// ─────────────────────────────────────────────
async function fetchLibrary(forceRefresh = false) {
  if (localStorage.getItem("hb_demo_mode") === "true") return window._demoLibrary || [];
  const ctx = getContentContext();
  // Invalidate cache if context switched since last fetch (Bug #8 fix)
  if (_cachedLibrary && _cachedLibraryContext !== ctx) { _cachedLibrary = null; }
  if (_cachedLibrary && !forceRefresh) return _cachedLibrary;
  try {
    const includeArchived = currentLibraryFilter === "archived";
    const res = await authFetch(`${BACKEND_URL}/library?context=${ctx}${includeArchived?"&include_archived=true":""}`);
    if (!res.ok) throw new Error(`${res.status}`);
    const data = await res.json();
    _cachedLibrary = data.items || [];
    _cachedLibraryContext = ctx;
    return _cachedLibrary;
  } catch(err) {
    if (err.message === "Session expired") throw err;
    _cachedLibrary = _cachedLibrary || [];
    return _cachedLibrary;
  }
}
async function apiSaveLibraryItem(niche, content, compliance) {
  const res = await authFetch(`${BACKEND_URL}/library`, { method:"POST", body:JSON.stringify({ niche, content, compliance, source:"manual", context:getContentContext() }) });
  if (!res.ok) throw new Error(`Save failed: ${res.status}`);
  _cachedLibrary = null;
  const item = (await res.json()).item;
  // Auto-send approval email so agent can approve from their phone.
  // Fire-and-forget — never blocks the UI if this fails.
  if (item && item.id && localStorage.getItem("hb_demo_mode") !== "true") {
    authFetch(`${BACKEND_URL}/library/${item.id}/send-approval`, { method:"POST" }).catch(() => {});
  }
  return item;
}
async function apiPatchLibraryItem(itemId, updates) {
  if (localStorage.getItem("hb_demo_mode") === "true") {
    if (window._demoLibrary) {
      const idx = window._demoLibrary.findIndex(x => String(x.id) === String(itemId));
      if (idx >= 0) { window._demoLibrary[idx] = { ...window._demoLibrary[idx], ...updates }; return window._demoLibrary[idx]; }
    }
    return { id:itemId, ...updates };
  }
  const res = await authFetch(`${BACKEND_URL}/library/${itemId}`, { method:"PATCH", body:JSON.stringify(updates) });
  if (!res.ok) throw new Error(`Patch failed: ${res.status}`);
  const data = await res.json();
  if (_cachedLibrary) {
    const idx = _cachedLibrary.findIndex(x => String(x.id) === String(itemId));
    if (idx >= 0) _cachedLibrary[idx] = data.item;
  }
  return data.item;
}
async function apiDeleteLibraryItem(itemId) {
  const res = await authFetch(`${BACKEND_URL}/library/${itemId}`, { method:"DELETE" });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
  if (_cachedLibrary) _cachedLibrary = _cachedLibrary.filter(x => String(x.id) !== String(itemId));
}

// ─────────────────────────────────────────────
// SECTION 9: DEMO MODE — ISOLATED, BACKUP-FIRST
// ─────────────────────────────────────────────
function activateDemoMode() {
  const d = DEMO_DATA;
  // Mark all GS steps done — Brooke's profile is complete, skip the intro flow
  // Always overwrite — demo must show Brooke's profile, never bleed Kevin's real setup through
  localStorage.setItem("hb_setup", JSON.stringify({
    agentName:d.agentName, businessName:d.businessName, brokerage:d.brokerage,
    market:d.market, serviceAreas:d.serviceAreas, shortBio:d.shortBio,
    brandVoice:d.brandVoice, wordsAvoid:d.wordsAvoid, wordsPrefer:d.wordsPrefer,
    designations:d.designations, languagePref:d.languagePref, disclaimer:d.disclaimer,
    primaryNiches:d.primaryNiches, audienceDescription:d.audienceDescription, platforms:d.platforms,
    // Zone of Greatness — makes demo generation output authentic and compelling
    originStory:d.originStory, signaturePerspective:d.signaturePerspective,
    unfairAdvantage:d.unfairAdvantage, notForClient:d.notForClient,
    // CTA configuration
    ctaMethods:d.ctaMethods||[], ctaType:d.ctaType, ctaUrl:d.ctaUrl, ctaLabel:d.ctaLabel,
  }));
  localStorage.setItem("hb_disclaimer", d.disclaimer);
  localStorage.setItem("hb_mls",        JSON.stringify(d.mlsNames || []));
  localStorage.setItem("hb_demo_mode",  "true");
  localStorage.setItem("hb_token",  "demo-token");
  localStorage.setItem("hb_user",   JSON.stringify({ id:0, name:d.agentName, email:"brooke@callahan-properties.com", brokerage:d.brokerage, role:"agent", agent_name:d.agentName }));
  window._demoLibrary  = [...d.library];
  window._demoSignals  = [...(d.signals || [])];

  // Demo banner
  const existing = el("demo-banner");
  if (existing) existing.remove();
  const banner = document.createElement("div");
  banner.id = "demo-banner";
  banner.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:9999;background:linear-gradient(90deg,#2563eb,#7c3aed);color:#fff;text-align:center;padding:6px 16px;font-size:12px;font-weight:600;letter-spacing:0.03em;display:flex;align-items:center;justify-content:center;gap:16px;";
  const hasBackup = !!localStorage.getItem("hb_admin_session_backup");
  banner.innerHTML = `<span>✦ DEMO — Brooke Callahan, Austin TX</span>
    <a href="https://app.homebridgegroup.co" style="color:#fff;opacity:0.85;text-decoration:underline;font-size:11px;">Create free account →</a>
    <button onclick="${hasBackup ? 'exitDemo()' : 'exitDemoToLogin()'}" style="background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.55);color:#fff;font-size:11px;font-weight:700;padding:3px 14px;border-radius:12px;cursor:pointer;font-family:inherit;letter-spacing:0.03em;">${hasBackup ? '← Exit Demo' : '← Back to login'}</button>`;
  document.body.insertBefore(banner, document.body.firstChild);
  const shell = document.querySelector(".app-shell");
  if (shell) shell.style.paddingTop = "34px";
}

function exitDemo() {
  const backup = JSON.parse(localStorage.getItem("hb_admin_session_backup") || "null");
  if (backup) {
    localStorage.setItem("hb_token", backup.token);
    localStorage.setItem("hb_user",  JSON.stringify(backup.user));
    localStorage.removeItem("hb_admin_session_backup");
  }
  // Purge all demo-written keys — none should survive into a real session
  ["hb_demo_mode","hb_setup","hb_disclaimer","hb_socials","hb_mls",
   "hb_recent_personas","hb_gs_state","hb_onboarding_complete","hb_demo_onb_done"].forEach(k => localStorage.removeItem(k));
  window._demoLibrary = null;
  window.location.replace("index.html");
}
function exitDemoToLogin() {
  ["hb_demo_mode","hb_setup","hb_disclaimer","hb_socials","hb_mls","hb_token","hb_user",
   "hb_recent_personas","hb_gs_state","hb_onboarding_complete","hb_admin_session_backup","hb_demo_onb_done"].forEach(k => localStorage.removeItem(k));
  window._demoLibrary = null;
  window.location.replace("login.html");
}

// ─────────────────────────────────────────────
// SECTION 10: BOOT SEQUENCE — SINGLE ASYNC FUNCTION
// ─────────────────────────────────────────────
async function boot() {
  const params     = new URLSearchParams(window.location.search);
  const demoParam  = params.get("demo");
  const firstParam = params.get("first");
  const viewParam  = params.get("view");

  // ── ?view=agent — arriving from approval email "Edit in App" or "Open App" link ──
  // Force agent context before bootForRole fires so super_admin doesn't land in admin panel
  if (viewParam === "agent") {
    setViewContext("agent");
    window._bootViewOverride = "agent";           // prevent bootForRole from resetting to admin
    window._bootPanel        = params.get("panel") || null; // e.g. "library" for post-approve routing
    window._bootItem         = params.get("item")  || null; // item_id to auto-open in broadcast panel
    window.history.replaceState({}, "", window.location.pathname);
  }

  // ── Step 1: Demo URL param → activate demo directly, land on Home panel ──
  // Do NOT route to onboarding.html — Brooke's profile is pre-built.
  // Onboarding is for real new agents, not demo prospects.
  if (demoParam) {
    const existingToken = localStorage.getItem("hb_token");
    const existingUser  = JSON.parse(localStorage.getItem("hb_user") || "null");
    // Save admin session BEFORE wiping anything
    if ((existingUser?.role === "admin" || existingUser?.role === "super_admin") && existingToken && existingToken !== "demo-token") {
      localStorage.setItem("hb_admin_session_backup", JSON.stringify({ token:existingToken, user:existingUser }));
    }
    localStorage.setItem("hb_demo_mode", "true");
    // Fall through to Step 5 (demo mode boot) below
  }

  // ── Step 2: Coming back from onboarding ──
  if (firstParam === "true") {
    window.history.replaceState({}, "", window.location.pathname);
    window._landOnGettingStarted = true;
  }

  const token         = localStorage.getItem("hb_token");
  const userRaw       = localStorage.getItem("hb_user");
  const user          = JSON.parse(userRaw || "null");
  const isDemoMode    = localStorage.getItem("hb_demo_mode") === "true";
  const hasAdminBackup= !!localStorage.getItem("hb_admin_session_backup");

  // ── Step 3: Real token → always clear demo state (admin or not) ──
  if (token && token !== "demo-token") {
    localStorage.removeItem("hb_demo_mode");
    const isDemoUser = user?.email?.includes("brooke@") || user?.email?.includes("homebridgedemo");
    if (isDemoUser) {
      localStorage.removeItem("hb_setup");
      localStorage.removeItem("hb_user");
      window.location.href = "login.html";
      return;
    }
    // Real user but hb_setup may be contaminated with demo data from a prior session
    try {
      const savedSetup = JSON.parse(localStorage.getItem("hb_setup") || "null");
      const demoName   = (DEMO_DATA?.agentName || "Brooke Callahan").toLowerCase();
      const setupName  = (savedSetup?.agentName || "").toLowerCase();
      const setupEmail = (savedSetup?.email || "").toLowerCase();
      if (savedSetup && (setupName === demoName || setupEmail.includes("brooke@"))) {
        localStorage.removeItem("hb_setup");
        localStorage.removeItem("hb_disclaimer");
      }
    } catch(e) { /* parse error — leave it */ }
  }

  // ── Step 4: No auth, no demo → login ──
  if (!token && !isDemoMode) {
    window.location.href = "login.html";
    return;
  }

  // ── Step 5: Demo mode ──
  if (isDemoMode) {
    activateDemoMode();
    const demoOnbDone = localStorage.getItem("hb_demo_onb_done") === "true";
    if (demoOnbDone) {
      renderNav("agent");
      updateAvatar();
      gsInjectAvatarLink();
      loadSetup();
      navigateTo("home-panel");
    } else {
      window.location.replace("onboarding.html");
    }
    return;
  }

  // ── Step 6: Real user ──
  if (!user) { window.location.href = "login.html"; return; }

  // Sync setup from server then boot
  // Always sync agent setup on boot — marketing context is handled separately
  // by _bootAsMarketing() which calls _setupGet() in marketing context.
  // Boot always lands in agent/admin context first, so this is always safe.
  try {
    const res = await authFetch(`${BACKEND_URL}/setup/get`);
    if (res.ok) {
      const data = await res.json();
      if (data.has_setup && data.setup) {
        const local   = getSaved();
        const merged  = { ...data.setup };
        const onbKeys = ["primaryNiches","audienceDescription","market","brandVoice","platforms","onboardingComplete"];
        onbKeys.forEach(k => {
          const lv = local[k], sv = merged[k];
          const empty = !sv || (Array.isArray(sv) && sv.length === 0) || sv === "";
          if (lv && empty) merged[k] = lv;
        });
        localStorage.setItem("hb_setup", JSON.stringify(merged));
        // Sync mlsNames from server into hb_mls so profile panel displays correctly
        if (Array.isArray(merged.mlsNames) && merged.mlsNames.length) {
          localStorage.setItem("hb_mls", JSON.stringify(merged.mlsNames));
        }
      }
    }
  } catch(e) { /* offline — use localStorage */ }

  // Sanitize setup data — remove corrupted niche entries (emails, empty strings, etc.)
  try {
    const setup = JSON.parse(localStorage.getItem("hb_setup") || "null");
    if (setup && Array.isArray(setup.primaryNiches)) {
      const cleaned = setup.primaryNiches.filter(n =>
        n && typeof n === "string" && !n.includes("@") && !n.includes(".com") && n.length < 80
      );
      if (cleaned.length !== setup.primaryNiches.length) {
        setup.primaryNiches = cleaned;
        localStorage.setItem("hb_setup", JSON.stringify(setup));
      }
    }
  } catch(e) {}
  // Sanitize hb_custom_niches — same check
  try {
    const custom = JSON.parse(localStorage.getItem("hb_custom_niches") || "[]");
    const cleanedCustom = custom.filter(n =>
      n && typeof n === "string" && !n.includes("@") && !n.includes(".com") && n.length < 80
    );
    if (cleanedCustom.length !== custom.length) {
      localStorage.setItem("hb_custom_niches", JSON.stringify(cleanedCustom));
    }
  } catch(e) {}

  // Check for OAuth callback params in URL — MUST run before bootForRole
  // so _bootViewOverride is set before bootForRole resets the view context
  checkOAuthCallback();
  bootForRole(user);
}

// ─────────────────────────────────────────────
// SECTION 11: ROLE / NAV MANAGEMENT
// ─────────────────────────────────────────────
const NAV_CONFIGS = {
  // Licensed agent — Home · Studio · Records · Identity · Profile
  agent: [
    { label:"Home",     target:"home-panel"          },
    { label:"Studio",   target:"content-engine-panel"},
    { label:"Records",  target:"library-panel"       },
    { label:"Identity", target:"setup-panel"         },
    { label:"Profile",  target:"profile-panel"       },
  ],
  // HB Marketing context
  marketing: [
    { label:"Identity",  target:"setup-panel"        },
    { label:"Studio",    target:"content-engine-panel"},
    { label:"Edit",      target:"workspace-panel"     },
    { label:"HB Content",  target:"library-panel"       },
    { label:"HB Activity", target:"distribution-panel"  },
    { label:"Profile",     target:"profile-panel"       },
  ],
  // HB Marketer — brand content only, no pill switcher
  hb_marketer: [
    { label:"Identity",  target:"setup-panel"         },
    { label:"Studio",    target:"content-engine-panel" },
    { label:"Edit",        target:"workspace-panel"      },
    { label:"HB Content",  target:"library-panel"        },
    { label:"HB Activity", target:"distribution-panel"   },
    { label:"Profile",     target:"profile-panel"        },
  ],
  // Broker — office overview
  broker: [
    { label:"Overview",   target:"broker-panel" },
    { label:"Agents",     target:"broker-panel" },
    { label:"Compliance", target:"broker-panel" },
    { label:"Identity",   target:"setup-panel"  },
  ],
  // Admin — platform management + optional agent
  admin: [
    { label:"Dashboard",   target:"admin-panel", section:"dashboard"  },
    { label:"Users",       target:"admin-panel", section:"users"      },
    { label:"Create User", target:"admin-panel", section:"create"     },
    { label:"Demo Links",  target:"admin-panel", section:"demo"       },
    { label:"Compliance",  target:"admin-panel", section:"compliance" },
  ],
  // Support — customer support view
  support: [
    { label:"Dashboard",   target:"admin-panel", section:"dashboard" },
    { label:"Users",       target:"admin-panel", section:"users"     },
  ],
  // Super admin — full platform view (Platform pill context)
  super_admin: [
    { label:"Dashboard",   target:"admin-panel", section:"dashboard"  },
    { label:"Users",       target:"admin-panel", section:"users"      },
    { label:"Create User", target:"admin-panel", section:"create"     },
    { label:"Demo Links",  target:"admin-panel", section:"demo"       },
    { label:"Audit Log",   target:"admin-panel", section:"audit"      },
    { label:"Compliance",  target:"admin-panel", section:"compliance" },
  ],
  // Office context (broker dashboard for super_admin/admin viewing)
  office: [
    { label:"Overview",   target:"broker-panel" },
    { label:"Agents",     target:"broker-panel" },
    { label:"Compliance", target:"broker-panel" },
    { label:"Identity",   target:"setup-panel"  },
  ],
  // Team context — standalone team lead dashboard
  team: [
    { label:"Overview",  target:"broker-panel" },
    { label:"Members",   target:"broker-panel" },
    { label:"Activity",  target:"broker-panel" },
    { label:"Identity",  target:"setup-panel"  },
  ],
  // Assistant — generate/draft for assigned agents only
  assistant: [
    { label:"Create",      target:"content-engine-panel" },
    { label:"Drafts",      target:"library-panel"        },
  ],
  // Partner Program — enrolled users only (see partner.js)
  partner: [
    { label:"Overview",  target:"partner-panel", section:"overview"  },
    { label:"Referrals", target:"partner-panel", section:"referrals" },
    { label:"Earnings",  target:"partner-panel", section:"earnings"  },
    { label:"Payouts",   target:"partner-panel", section:"payouts"   },
  ],
};

function getViewContext() {
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return "agent";
  const role = user.role || "agent";
  // Single-context roles — no switching
  if (role === "agent")     return "agent";
  if (role === "assistant") return "assistant";
  if (role === "broker")    return "office";
  if (role === "team")      return "team";
  if (role === "support")   return "support";
  // Multi-context roles: super_admin and admin use saved preference
  const saved = localStorage.getItem("hb_view_context");
  if (saved) return saved;
  // Defaults
  if (role === "super_admin") return "super_admin";
  if (role === "admin")       return "admin";
  return role;
}
function setViewContext(ctx) { localStorage.setItem("hb_view_context", ctx); }

function renderNav(ctx) {
  const linksEl = el("top-nav-links");
  if (!linksEl) return;
  const config = NAV_CONFIGS[ctx] || NAV_CONFIGS.agent;
  linksEl.innerHTML = config.map(item =>
    `<button class="nav-button" data-target="${item.target}" data-section="${item.section||''}">${item.label}</button>`
  ).join("");
  linksEl.querySelectorAll(".nav-button").forEach(btn => {
    btn.addEventListener("click", () => {
      navigateTo(btn.dataset.target);
      if (btn.dataset.section) showAdminSection(btn.dataset.section);
      linksEl.querySelectorAll(".nav-button").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });
}

// Show one admin sub-section, hide the rest.
// Lazy-loads users, demo tokens, and audit log on first view.
function showAdminSection(section) {
  ["dashboard","users","create","demo","audit","compliance"].forEach(s => {
    const sec = el(`admin-section-${s}`);
    if (sec) sec.style.display = s === section ? "" : "none";
  });
  // Highlight the matching nav button
  document.querySelectorAll(".nav-button[data-section]").forEach(b => {
    b.classList.toggle("active", b.dataset.section === section);
  });
  if (section === "dashboard")  loadAdminStats();
  if (section === "users")      loadAdminUsers();
  if (section === "demo")       loadDemoTokens();
  if (section === "audit")      loadAuditLog();
  if (section === "compliance") loadComplianceStatus();
}

function bootForRole(user, fromPill) {
  const role = user.role || "agent";
  // On hard boot reset super_admin and admin to their platform/admin context
  if (role === "super_admin" && !fromPill && !window._bootViewOverride) setViewContext("super_admin");
  if (role === "admin"       && !fromPill && !window._bootViewOverride) setViewContext("admin");
  delete window._bootViewOverride;
  const ctx = getViewContext();
  renderNav(ctx);
  updateAvatar();
  gsInjectAvatarLink();
  renderViewSwitcher();

  if (window._landOnGettingStarted) {
    delete window._landOnGettingStarted;
    loadSetup();
    gsRender();
    fetchAndRenderScore();
    navigateTo("getting-started-panel");
    return;
  }
  if (window._landOnSetup) {
    delete window._landOnSetup;
    navigateTo("setup-panel");
    return;
  }
  // Platform/admin contexts → admin panel
  if (ctx === "super_admin" || ctx === "admin" || ctx === "support") {
    navigateTo("admin-panel");
    loadAdminDashboard();
    return;
  }
  // Office context → broker panel
  if (ctx === "office" || ctx === "team" || role === "broker" || role === "team") {
    renderNav("office");
    navigateTo("broker-panel");
    loadBrokerDashboard();
    return;
  }
  // Assistant
  if (role === "assistant") {
    renderNav("assistant");
    navigateTo("content-engine-panel");
    return;
  }
  // HB Marketing / HB Marketer context
  if (ctx === "marketing" || role === "hb_marketer") {
    setViewContext("marketing");
    renderNav("marketing");
    _bootAsMarketing();
    return;
  }
  // Partner Program context (see partner.js)
  if (ctx === "partner") {
    renderNav("partner");
    navigateTo("partner-panel");
    return;
  }
  // Agent context (default)
  _bootAsAgent();
  // Initialize Jordan FAB with correct name after boot
  _initJordanFAB();
}

function _initJordanFAB() {
  const name = jordanName();
  const fabLabel = document.getElementById("jordan-fab-label");
  const fabAvatar = document.querySelector("#jordan-fab .jfab-avatar");
  const panelAvatar = document.getElementById("jordan-panel-avatar");
  const jwmAvatar = document.getElementById("jwm-avatar");
  if (fabLabel) fabLabel.textContent = `Ask ${name}`;
  const initial = name.charAt(0).toUpperCase();
  if (fabAvatar) fabAvatar.textContent = initial;
  if (panelAvatar) { panelAvatar.textContent = initial; }
  if (jwmAvatar) jwmAvatar.textContent = initial;
  const fab = document.getElementById("jordan-fab");
  if (fab) fab.title = `Ask ${name}`;
}

function _bootAsAgent() {
  const saved     = getSaved();
  const onbDone   = localStorage.getItem("hb_onboarding_complete") === "true";
  const isNewUser = !onbDone && !saved.agentName && !(Array.isArray(saved.primaryNiches) && saved.primaryNiches.length);
  fetchAndRenderScore();
  loadSetup();
  const bootPanel = window._bootPanel;
  const bootItem  = window._bootItem;
  delete window._bootPanel;
  delete window._bootItem;

  // Arriving from approval email with a specific item — open it directly in broadcast panel
  if (bootItem) {
    navigateTo("library-panel");
    renderLibrary();
    // Give library a moment to render, then find and open the item
    setTimeout(async () => {
      const lib  = await fetchLibrary().catch(() => []);
      const item = lib.find(x => String(x.id) === String(bootItem));
      if (item) openReviewModal(item);
    }, 600);
    return;
  }

  if (bootPanel === "library") {
    navigateTo("library-panel");
  } else if (isNewUser) {
    navigateTo("getting-started-panel");
    // First login — show Jordan naming screen before welcome modal
    if (!jordanNamingDone()) {
      setTimeout(() => showJordanNamingScreen(), 600);
    }
  } else {
    navigateTo("home-panel");
    // Returning user who completed naming but not welcome — show welcome
    if (jordanNamingDone() && !jordanWelcomeDone()) {
      setTimeout(() => showJordanWelcomeModal(), 800);
    }
  }
}

// ── HomeBridge Marketing Context ──
// Uses hb_hb_setup key to store company profile separately from agent profile
const HB_MARKETING_KEY = "hb_hb_setup";

const HB_MARKETING_PROFILE = {
  agentName:         "HomeBridge Group",
  brokerage:         "",
  market:            "Real Estate Technology",
  businessName:      "HomeBridge Group",
  shortBio:          "HomeBridge is the AI-powered content platform that keeps real estate professionals visible, compliant, and trusted. Built for agents. Designed for the age of authenticity.",
  brandVoice:        "Authoritative but accessible. Forward-thinking. No jargon. Speaks to the future of real estate without dismissing the present. Never corporate. Always direct.",
  wordsAvoid:        "synergy, leverage, disrupt, hustle, game-changer",
  wordsPrefer:       "trusted, verified, authentic, compliant, visible",
  disclaimer:        "HomeBridge Group · AI-powered content platform for real estate professionals · homebridgegroup.co",
  primaryNiches:     ["Broker & Office Management", "Agent Productivity & Technology", "Real Estate Compliance", "PropTech & Innovation", "Mortgage & Lending"],
  languagePref:      "english",
  platforms:         [
    { id: "linkedin", name: "LinkedIn" },
  ],
  serviceAreas:      ["United States", "Canada"],
  audienceDescription: "Real estate brokers, office managers, and team leads at independent and franchise brokerages. Secondary: PropTech investors, mortgage professionals, compliance officers.",
  hbOrgUrn:          "urn:li:organization:51723296",  // HomeBridge LinkedIn Company Page
};

function _bootAsMarketing() {
  // Reset category filter — marketing uses its own niche structure
  activeCategoryFilter = null;
  loadMarketingSetup().then(() => {
    fetchAndRenderScore();
    navigateTo("setup-panel");
  });
}

async function loadMarketingSetup() {
  // Pull from server first (marketing-setup/get reads hb_marketing_setup_json,
  // never agent_setup), then merge with localStorage defaults.
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(HB_MARKETING_KEY) || "null") || {}; } catch(e) {}

  // Attempt server sync — if it returns data, it wins over stale localStorage
  if (localStorage.getItem("hb_demo_mode") !== "true") {
    try {
      const res = await authFetch(`${BACKEND_URL}/marketing-setup/get`);
      if (res.ok) {
        const data = await res.json();
        if (data.has_setup && data.setup && Object.keys(data.setup).length > 0) {
          saved = data.setup;
          localStorage.setItem(HB_MARKETING_KEY, JSON.stringify(saved));
        }
      }
    } catch(e) { /* offline — use localStorage */ }
  }

  // Merge defaults with any saved overrides
  const profile = Object.assign({}, HB_MARKETING_PROFILE, saved);
  // Apply to app state
  selectedPrimaryNiches = Array.isArray(profile.primaryNiches) ? profile.primaryNiches : HB_MARKETING_PROFILE.primaryNiches;
  selectedSubNiches = [];
  // Populate fields
  [["market","market"],["business-name","businessName"],["short-bio","shortBio"],["brand-voice","brandVoice"],["words-avoid","wordsAvoid"],["words-prefer","wordsPrefer"]].forEach(([id,key]) => {
    const e = el(id); if (e && profile[key]) e.value = profile[key];
  });
  const discEl = el("profile-disclaimer"); if (discEl) discEl.value = profile.disclaimer || "";
  localStorage.setItem("hb_disclaimer", profile.disclaimer || "");
  // Store to marketing key — getSaved() will read this when context is marketing
  localStorage.setItem(HB_MARKETING_KEY, JSON.stringify(profile));
  renderPrimaryNicheChips();
  renderCustomNicheChips();
}

function saveMarketingSetup() {
  // Save the current state back to hb_hb_setup in localStorage
  const saved = JSON.parse(localStorage.getItem(HB_MARKETING_KEY) || "{}");
  saved.primaryNiches = selectedPrimaryNiches;
  saved.shortBio      = el("short-bio")?.value.trim() || saved.shortBio;
  saved.brandVoice    = el("brand-voice")?.value.trim() || saved.brandVoice;
  saved.wordsAvoid    = el("words-avoid")?.value.trim() || saved.wordsAvoid;
  saved.wordsPrefer   = el("words-prefer")?.value.trim() || saved.wordsPrefer;
  saved.market        = el("market")?.value.trim() || saved.market;
  const disc = el("profile-disclaimer")?.value.trim();
  if (disc) { saved.disclaimer = disc; localStorage.setItem("hb_disclaimer", disc); }
  localStorage.setItem(HB_MARKETING_KEY, JSON.stringify(saved));
  // _setupSave routes to /marketing-setup/save in marketing context —
  // writes to users.hb_marketing_setup_json, never touches agent_setup.
  if (localStorage.getItem("hb_demo_mode") !== "true") {
    _setupSave(saved);
  }
  showToast("✓ HomeBridge profile saved");
}

function restoreAgentSetup() {
  // Context-aware getSaved() handles data separation — just reset the category filter
  activeCategoryFilter = null;
  // Clean up legacy backup key if present from old sessions
  localStorage.removeItem("hb_agent_setup_backup");
}

function renderViewSwitcher() {
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const role = user.role || "agent";
  // hb_marketer sees only HB Marketing — no pill switcher ever
  if (role === "hb_marketer") return;
  // Agents without partner enrollment have no context to switch — exit early
  // Enrolled agents get a minimal 2-pill switcher (My Work ↔ Partner)
  if (role === "agent" && !user.partner_tier) return;
  const existing = el("view-switcher");
  if (existing) existing.remove();

  const ctx     = getViewContext();
  const pill    = document.createElement("div");
  pill.id       = "view-switcher";
  pill.style.cssText = "display:flex;align-items:center;gap:4px;background:var(--surface);border:1.5px solid var(--border);border-radius:20px;padding:3px;margin-right:8px;";

  // Simple pill switcher — only show what's needed
  const isLicensed = user.is_licensed !== 0; // default true — only hide if explicitly 0
  let opts = [];
  if (role === "super_admin" || role === "admin") {
    opts = [
      { val:"super_admin", label:"⚙ Platform"    },
    ];
    if (isLicensed) opts.push({ val:"agent",     label:"◈ Agent"        });
    opts.push(       { val:"marketing", label:"◈ HB Marketing" });
    if (isLicensed) opts.push({ val:"office",    label:"⌂ My Office"    });
    if (isLicensed) opts.push({ val:"team",      label:"◈ My Team"      });
    opts.push(                 { val:"partner",   label:"♦ Partner"      });
  } else if (role === "broker") {
    opts = [
      { val:"office", label:"⌂ My Office" },
    ];
    if (isLicensed) opts.push({ val:"agent",   label:"◈ Agent"   });
    opts.push(                 { val:"partner", label:"♦ Partner" });
  } else if (role === "agent" && user.partner_tier) {
    // Enrolled agent — show their two contexts
    opts = [
      { val:"agent",   label:"◈ Agent"   },
      { val:"partner", label:"♦ Partner"  },
    ];
  }

  opts.forEach(({ val, label }) => {
    const btn = document.createElement("button");
    btn.textContent = label;
    const active = ctx === val;
    btn.style.cssText = `background:${active?"var(--blue)":"transparent"};color:${active?"#fff":"var(--ink-3)"};border:none;border-radius:16px;padding:4px 14px;font-size:12px;font-weight:${active?"700":"500"};font-family:inherit;cursor:pointer;transition:all 0.15s;`;
    btn.addEventListener("click", () => {
      if (getViewContext() === val) return;
      // Restore agent setup if switching away from marketing
      if (getViewContext() === "marketing") restoreAgentSetup();
      setViewContext(val);
      renderViewSwitcher();
      bootForRole(user, true);
    });
    pill.appendChild(btn);
  });

  const topNavRight = document.querySelector(".top-nav-right");
  const avatarWrap  = el("avatar-wrap");
  if (topNavRight) topNavRight.appendChild(pill);
}

function updateAvatar() {
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");
  const saved = getSaved();
  const ctx   = getViewContext();

  const nameEl  = el("sidebar-avatar-name");
  const brokeEl = el("sidebar-avatar-brokerage");
  const initEl  = el("sidebar-avatar-initials");

  let displayName = "Agent", subName = "";
  if (ctx === "super_admin") {
    displayName = user?.agent_name || user?.email?.split("@")[0] || "Platform";
    subName     = "Platform Admin";
  } else if (ctx === "admin") {
    displayName = user?.agent_name || user?.email?.split("@")[0] || "Admin";
    subName     = "Administrator";
  } else if (ctx === "support") {
    displayName = user?.agent_name || user?.email?.split("@")[0] || "Support";
    subName     = "Customer Support";
  } else if (ctx === "team") {
    displayName = saved.businessName || user?.brokerage || "Your Team";
    subName     = "Team Dashboard";
  } else if (ctx === "office" || ctx === "broker") {
    displayName = saved.businessName || user?.brokerage || "Your Office";
    subName     = "Office Dashboard";
  } else if (ctx === "marketing") {
    displayName = "HomeBridge Group";
    subName     = "Company Marketing";
  } else if (ctx === "partner") {
    displayName = saved.agentName || user?.agent_name || user?.name || "Partner";
    subName     = "Partner Program";
  } else {
    displayName = saved.agentName || user?.agent_name || user?.name || "Agent";
    subName     = saved.brokerage || user?.brokerage || "";
  }

  if (nameEl)  nameEl.textContent  = displayName;
  if (brokeEl) brokeEl.textContent = subName;

  // Show profile photo if available and NOT in demo mode, otherwise show initials
  const profilePhoto = localStorage.getItem("hb_profile_photo");
  const isDemoMode   = localStorage.getItem("hb_demo_mode") === "true";
  if (initEl) {
    if (profilePhoto && !isDemoMode) {
      initEl.style.backgroundImage = `url(${profilePhoto})`;
      initEl.style.backgroundSize  = "cover";
      initEl.style.backgroundPosition = "center";
      initEl.textContent = "";
    } else {
      initEl.style.backgroundImage = "";
      initEl.textContent = getInitials(displayName);
    }
  }

  const ddName  = el("dd-name");
  const ddEmail = el("dd-email");
  if (ddName)  ddName.textContent  = displayName;
  if (ddEmail) ddEmail.textContent = user?.email || "";
}

// ─────────────────────────────────────────────
// PROFILE PHOTO UPLOAD
// Canvas-based conversion handles HEIC, JPEG, PNG, WebP from any device.
// Stores result as JPEG base64 in localStorage under hb_profile_photo.
// Also saves to backend for video rendering (Session 49).
// ─────────────────────────────────────────────
function triggerProfilePhotoUpload() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";  // accepts everything; canvas handles conversion
  input.onchange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Size guard — reject files over 15MB before trying to process
    if (file.size > 15 * 1024 * 1024) {
      alert("That photo is a bit large. Please choose a photo under 15MB.");
      return;
    }
    try {
      const base64Jpeg = await _convertImageToJpeg(file);
      // Save to localStorage for navbar avatar display (existing behaviour)
      localStorage.setItem("hb_profile_photo", base64Jpeg);
      updateAvatar();
      // Also save to backend so video rendering can access it via signed URL.
      // Non-blocking — failure here does not affect the photo display.
      const isDemo = localStorage.getItem("hb_demo_mode") === "true";
      if (!isDemo) {
        authFetch(`${BACKEND_URL}/profile/photo`, {
          method: "POST",
          body: JSON.stringify({ photo_b64: base64Jpeg }),
        }).then(res => {
          if (res.ok) {
            console.log("[Photo] Profile photo saved to backend for video rendering.");
          } else {
            console.warn("[Photo] Backend photo save returned non-OK status — video rendering may not be available.");
          }
        }).catch(err => {
          console.warn("[Photo] Backend photo save failed (non-blocking):", err.message);
        });
      }
    } catch (err) {
      alert("This photo format isn't supported. Try taking a new photo or screenshot and uploading that instead.");
    }
  };
  input.click();
}

function _convertImageToJpeg(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        // Constrain to 400×400 max — enough for avatar display and DALL-E reference
        const MAX = 400;
        let w = img.width, h = img.height;
        if (w > h) { h = Math.round(h * MAX / w); w = MAX; }
        else       { w = Math.round(w * MAX / h); h = MAX; }
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        canvas.getContext("2d").drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      };
      img.onerror = () => reject(new Error("Image decode failed"));
      img.src = e.target.result;
    };
    reader.onerror = () => reject(new Error("File read failed"));
    reader.readAsDataURL(file);
  });
}

// ─────────────────────────────────────────────
// SECTION 12: NAVIGATION
// ─────────────────────────────────────────────
function navigateTo(target) {
  _currentPanel = target; // Jordan uses this for context-aware messages
  document.querySelectorAll(".nav-button").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  const panel = el(target);
  if (panel) panel.classList.add("active");
  const btn = document.querySelector(`.nav-button[data-target="${target}"]`);
  if (btn) btn.classList.add("active");
  // Update Jordan button tooltip
  const jordanBtn = document.getElementById("jordan-fab");
  if (jordanBtn) {
    const msg = jordanMessageFor(target);
    jordanBtn.title = msg ? `Ask ${jordanName()} — ${msg.title}` : `Ask ${jordanName()}`;
  }

  // Panel-specific loaders
  // Clear signal refresh timer when leaving home panel
  if (target !== "home-panel" && window._signalRefreshTimer) {
    clearInterval(window._signalRefreshTimer);
    window._signalRefreshTimer = null;
  }
  if (target === "home-panel") {
    renderHomeDashboard();
    // Refresh signal zone every 30 minutes while home panel is active
    if (window._signalRefreshTimer) clearInterval(window._signalRefreshTimer);
    window._signalRefreshTimer = setInterval(() => {
      if (document.getElementById('home-panel')?.classList.contains('active') ||
          document.getElementById('home-panel')?.style.display !== 'none') {
        _refreshSignalZoneOnly();
      }
    }, 30 * 60 * 1000);
  }
  if (target === "setup-panel")          { loadSetup(); renderScheduleUI(); setTimeout(clearAutofill, 200); }
  if (target === "profile-panel") {
    // Refresh user data from server first so fields always show current data
    // This handles cases where localStorage is stale or was cleared
    const isDemo = localStorage.getItem("hb_demo_mode") === "true";
    if (!isDemo) {
      _setupGet().then(async r => {
        if (!r.ok) return;
        const data = await r.json();
        if (data.setup) {
          const saved = getSaved();
          const merged = { ...saved, ...data.setup };
          localStorage.setItem(getSetupKey(), JSON.stringify(merged));
        }
      }).catch(()=>{}).finally(() => {
        const s = getSaved(); const u = JSON.parse(localStorage.getItem("hb_user")||"null");
        const hasData = !!(u?.agent_name && (s.market || s.shortBio || s.disclaimer));
        if (_profileMode !== "full" && !hasData) _profileMode = "guided";
        else if (hasData) _profileMode = "full";
        renderProfilePanel();
        setTimeout(clearAutofill, 300);
      });
      return; // renderProfilePanel called in finally above
    }
    const s = getSaved(); const u = JSON.parse(localStorage.getItem("hb_user")||"null");
    const hasData = !!(u?.agent_name && (s.market || s.shortBio || s.disclaimer));
    if (_profileMode !== "full" && !hasData) _profileMode = "guided";
    else if (hasData) _profileMode = "full";
    renderProfilePanel();
    setTimeout(clearAutofill, 200);
  }
  if (target === "content-engine-panel") {
    ceInit();
  }
  if (target === "library-panel")        renderLibrary();
  if (target === "workspace-panel")      { /* keep current content */ }
  if (target === "distribution-panel")   loadResults();
  if (target === "broker-panel")         loadBrokerDashboard();
  if (target === "partner-panel")        renderPartnerDashboard(); // partner.js
  // admin sub-sections handled by showAdminSection; loadAdminDashboard called from bootForRole
  if (target === "getting-started-panel") { obInit(); }
  if (target === "profile-panel") loadPlatformConnections();
}

// ─────────────────────────────────────────────
// SECTION 12B: AUTOFILL GUARD + AUTOSAVE
// ─────────────────────────────────────────────

// ── Debounce utility ──
function debounce(fn, delay) {
  let t;
  return function(...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), delay); };
}

// ── Autosave indicator ──
// Brief "✓ Saved" that appears in the profile panel header then fades
function showAutoSaved() {
  const ind = el("autosave-indicator");
  if (!ind) return;
  ind.textContent = "✓ Saved";
  ind.style.opacity = "1";
  clearTimeout(ind._t);
  ind._t = setTimeout(() => { ind.style.opacity = "0"; }, 2000);
}

// ── Autosave: account info ──
// Saves name/brokerage/email/phone/notification email/MLS on blur
// Validates required fields silently — shows inline error only if missing
async function autoSaveAccountInfo() {
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  const agent_name = el("profile-name")?.value.trim() || "";
  const email      = el("profile-email")?.value.trim() || "";
  const brokerage  = el("profile-brokerage")?.value.trim() || "";
  const phone      = el("profile-phone")?.value.trim() || "";
  const notifEmail = el("profile-notification-email")?.value.trim() || "";

  // SMS consent + frequency
  const smsConsent    = el("sms-consent-checkbox")?.checked || false;
  const smsFrequency  = document.querySelector("input[name='sms-frequency']:checked")?.value || "daily";
  // If consent unchecked, clear the approval phone so SMS stops
  const approvalPhone = smsConsent && phone ? phone : "";

  // Always save to localStorage regardless of whether required fields are set
  const user = JSON.parse(localStorage.getItem("hb_user") || "{}");
  if (agent_name) user.agent_name = agent_name;
  if (brokerage)  user.brokerage  = brokerage;
  if (phone)      user.phone      = phone;
  if (notifEmail !== undefined) user.notification_email = notifEmail || null;
  localStorage.setItem("hb_user", JSON.stringify(user));
  updateAvatar();

  const cs = getSaved();
  if (agent_name) cs.agentName = agent_name;
  if (brokerage)  cs.brokerage = brokerage;
  // Persist SMS prefs to setup so they survive sessions
  cs.smsConsentGiven = smsConsent;
  cs.smsFrequency    = smsFrequency;
  cs.approvalPhone   = approvalPhone;

  // MLS — always save regardless of other fields
  const mls = [
    el("profile-mls-1")?.value.trim()||"",
    el("profile-mls-2")?.value.trim()||"",
    el("profile-mls-3")?.value.trim()||""
  ].filter(Boolean);
  localStorage.setItem("hb_mls", JSON.stringify(mls));
  cs.mlsNames = mls;
  localStorage.setItem(getSetupKey(), JSON.stringify(cs));
  showAutoSaved();
  // Also show inline confirmation if the save button exists
  const acctMsg = el("account-saved-msg");
  if (acctMsg) { acctMsg.style.display = "block"; setTimeout(() => { acctMsg.style.display = "none"; }, 2500); }

  if (isDemo) return;

  // Only fire backend calls if we have the minimum required fields
  if (!agent_name || !email) return;

  authFetch(`${BACKEND_URL}/auth/profile`, {
    method:"POST", body:JSON.stringify({ agent_name, brokerage, email, phone })
  }).then(async r => {
    if (r.ok) {
      const data = await r.json();
      const updated = { ...JSON.parse(localStorage.getItem("hb_user")||"{}"), ...data.user };
      localStorage.setItem("hb_user", JSON.stringify(updated));
      updateAvatar();
    }
  }).catch(()=>{});

  // Notification email — always save to server if field exists, not just on change
  authFetch(`${BACKEND_URL}/auth/profile/notification-email`, {
    method:"POST", body:JSON.stringify({ notification_email: notifEmail || null })
  }).then(r => {
    if (r.ok) {
      const u = JSON.parse(localStorage.getItem("hb_user")||"{}");
      u.notification_email = notifEmail || null;
      localStorage.setItem("hb_user", JSON.stringify(u));
    }
  }).catch(()=>{});

  _setupSave(cs);
  gsMarkDone(1);
}

// ── Autosave: identity fields (factual only — NOT Zone of Greatness) ──
// ─────────────────────────────────────────────
// MULTI-CTA BUILDER
// ─────────────────────────────────────────────

const CTA_TYPES = [
  { value: "calendar", label: "📅 Calendar Booking", placeholder: "e.g. calendly.com/kevin-lundy/15min",   urlLabel: "Booking URL" },
  { value: "text",     label: "💬 Direct Text",      placeholder: "e.g. 720-555-0100",                    urlLabel: "Phone number" },
  { value: "phone",    label: "📞 Phone Call",        placeholder: "e.g. 720-555-0100",                    urlLabel: "Phone number" },
  { value: "email",    label: "✉️ Email",             placeholder: "e.g. kevin@homebridgegroup.co",        urlLabel: "Email address" },
  { value: "website",  label: "🌐 Website",           placeholder: "e.g. homebridgegroup.co",              urlLabel: "Website URL" },
  { value: "authority",label: "🔗 Authority Page",    placeholder: "e.g. kevin-lundy-denver.homebridgegroup.co", urlLabel: "Page URL" },
];

function _ctaTypeOptions(selected) {
  return CTA_TYPES.map(t =>
    `<option value="${t.value}"${selected===t.value?" selected":""}>${t.label}</option>`
  ).join("");
}

function _ctaPlaceholder(type) {
  return (CTA_TYPES.find(t=>t.value===type)||CTA_TYPES[0]).placeholder;
}

function _ctaUrlLabel(type) {
  return (CTA_TYPES.find(t=>t.value===type)||CTA_TYPES[0]).urlLabel;
}

function renderCtaMethods() {
  const list = el("cta-methods-list"); if (!list) return;
  const addBtn = el("cta-add-method-btn");
  const saved = getSaved();

  // Migrate legacy single-CTA to array format
  let methods = saved.ctaMethods;
  if (!Array.isArray(methods) || methods.length === 0) {
    if (saved.ctaType || saved.ctaUrl) {
      methods = [{ type: saved.ctaType||"calendar", url: saved.ctaUrl||"", label: saved.ctaLabel||"" }];
    } else {
      methods = [{ type: "calendar", url: "", label: "" }];
    }
  }

  list.innerHTML = methods.map((m, i) => _ctaMethodRow(m, i, methods.length)).join("");

  // Show/hide add button
  if (addBtn) addBtn.style.display = methods.length >= 3 ? "none" : "block";

  // Wire events
  list.querySelectorAll(".cta-type-sel").forEach(sel => {
    sel.addEventListener("change", () => { _ctaTypeChanged(sel); _ctaSave(); });
  });
  list.querySelectorAll(".cta-url-inp,.cta-label-inp").forEach(inp => {
    inp.addEventListener("input", debounce(_ctaSave, 600));
  });
  list.querySelectorAll(".cta-remove-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx);
      const saved = getSaved();
      const methods = saved.ctaMethods || [];
      methods.splice(idx, 1);
      saved.ctaMethods = methods;
      localStorage.setItem(getSetupKey(), JSON.stringify(saved));
      renderCtaMethods();
      showAutoSaved();
      _setupSave(saved);
    });
  });
}

function _ctaMethodRow(m, idx, total) {
  const type = m.type || "calendar";
  const urlPh = _ctaPlaceholder(type);
  const urlLbl = _ctaUrlLabel(type);
  return `
    <div class="cta-method-row" style="background:var(--bg-sunken);border:1px solid var(--border);border-radius:10px;padding:12px 14px;position:relative;">
      ${total > 1 ? `<button class="cta-remove-btn" data-idx="${idx}"
        style="position:absolute;top:8px;right:10px;background:none;border:none;font-size:14px;color:var(--ink-4);cursor:pointer;line-height:1;padding:2px 4px;border-radius:4px;transition:color .15s;"
        onmouseover="this.style.color='var(--red)'" onmouseout="this.style.color='var(--ink-4)'"
        title="Remove this method">×</button>` : ""}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:8px;">
        <div>
          <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-4);margin-bottom:4px;">Type</div>
          <div class="select-wrapper" style="width:100%;">
            <select class="cta-type-sel" data-idx="${idx}"
              style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:13px;background:var(--surface);color:var(--ink);outline:none;">
              ${_ctaTypeOptions(type)}
            </select>
            <span class="select-arrow">▾</span>
          </div>
        </div>
        <div>
          <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-4);margin-bottom:4px;">Label <span style="font-weight:400;text-transform:none;letter-spacing:0;">optional</span></div>
          <input class="cta-label-inp" data-idx="${idx}" type="text"
            value="${_escHtml(m.label||"")}"
            placeholder="e.g. Book a free 15-min call"
            style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:13px;background:var(--surface);color:var(--ink);outline:none;"/>
        </div>
      </div>
      <div>
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-4);margin-bottom:4px;" id="cta-url-lbl-${idx}">${urlLbl}</div>
        <input class="cta-url-inp" data-idx="${idx}" type="text"
          value="${_escHtml(m.url||"")}"
          placeholder="${urlPh}"
          style="width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:13px;background:var(--surface);color:var(--ink);outline:none;"/>
      </div>
    </div>`;
}

function _ctaTypeChanged(sel) {
  const idx  = parseInt(sel.dataset.idx);
  const type = sel.value;
  const row  = sel.closest(".cta-method-row");
  if (!row) return;
  const urlInp = row.querySelector(".cta-url-inp");
  const urlLbl = document.getElementById(`cta-url-lbl-${idx}`);
  if (urlInp) urlInp.placeholder = _ctaPlaceholder(type);
  if (urlLbl) urlLbl.textContent  = _ctaUrlLabel(type);
}

function _ctaSave() {
  const list = el("cta-methods-list"); if (!list) return;
  const rows = list.querySelectorAll(".cta-method-row");
  const methods = [];
  rows.forEach((row, i) => {
    const type  = row.querySelector(".cta-type-sel")?.value  || "calendar";
    const url   = row.querySelector(".cta-url-inp")?.value.trim()   || "";
    const label = row.querySelector(".cta-label-inp")?.value.trim() || "";
    methods.push({ type, url, label });
  });
  const saved = getSaved();
  saved.ctaMethods = methods;
  // Keep legacy fields in sync with first method for backward compat
  if (methods.length > 0) {
    saved.ctaType  = methods[0].type;
    saved.ctaUrl   = methods[0].url;
    saved.ctaLabel = methods[0].label;
  }
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  showAutoSaved();
  _setupSave(saved);
}

function _ctaAddMethod() {
  const saved = getSaved();
  const methods = Array.isArray(saved.ctaMethods) ? saved.ctaMethods : [];
  if (methods.length >= 3) return;
  methods.push({ type: "calendar", url: "", label: "" });
  saved.ctaMethods = methods;
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  renderCtaMethods();
}

function getCtaMethods() {
  const saved = getSaved();
  if (Array.isArray(saved.ctaMethods) && saved.ctaMethods.length > 0) {
    return saved.ctaMethods.filter(m => m.url && m.url.trim());
  }
  // Fallback to legacy single fields
  if (saved.ctaUrl) {
    return [{ type: saved.ctaType||"calendar", url: saved.ctaUrl, label: saved.ctaLabel||"" }];
  }
  return [];
}



function autoSaveIdentityFields() {
  const saved = getSaved();
  saved.businessName        = el("business-name")?.value.trim()        || saved.businessName        || "";
  saved.market              = el("market")?.value.trim()               || saved.market              || "";
  saved.state               = el("setup-state")?.value                || saved.state               || "";
  saved.shortBio            = el("short-bio")?.value.trim()            || saved.shortBio            || "";
  saved.brandVoice          = el("brand-voice")?.value.trim()          || saved.brandVoice          || "";
  saved.wordsAvoid          = el("words-avoid")?.value.trim()          || saved.wordsAvoid          || "";
  saved.wordsPrefer         = el("words-prefer")?.value.trim()         || saved.wordsPrefer         || "";
  saved.audienceDescription = el("audience-description")?.value.trim() || saved.audienceDescription || "";
  // Zone of Greatness — preserve existing values if field is currently blank
  const zogOrigin  = el("origin-story")?.value.trim();
  const zogSig     = el("signature-perspective")?.value.trim();
  const zogUnfair  = el("unfair-advantage")?.value.trim();
  const zogNotFor  = el("not-for-client")?.value.trim();
  if (zogOrigin)  saved.originStory          = zogOrigin;
  if (zogSig)     saved.signaturePerspective = zogSig;
  if (zogUnfair)  saved.unfairAdvantage      = zogUnfair;
  if (zogNotFor)  saved.notForClient         = zogNotFor;
  // CTA methods saved via _ctaSave() — called by renderCtaMethods() event listeners
  saved.serviceAreas        = getServiceAreas();
  saved.designations        = getDesignations();
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  showAutoSaved();
  if (localStorage.getItem("hb_demo_mode") !== "true") {
    _setupSave(saved);
  }
}

// ── Autosave: disclaimer ──
function autoSaveDisclaimer() {
  const v = el("profile-disclaimer")?.value.trim() || "";
  if (!v) return;
  localStorage.setItem("hb_disclaimer", v);
  const saved = getSaved(); saved.disclaimer = v;
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  showAutoSaved();
  gsMarkDone(1);
  if (localStorage.getItem("hb_demo_mode") !== "true") {
    _setupSave(saved);
  }
}

// ── Autosave: recruiting fields ──
function autoSaveRecruitingFields() {
  const enabled = el("recruiting-enabled")?.checked || false;
  const cta     = el("recruiting-cta")?.value.trim() || "";
  // Show/hide custom message field
  const field = el("recruiting-cta-field");
  if (field) field.style.display = enabled ? "block" : "none";
  // Save
  const saved = getSaved();
  saved.recruitingEnabled = enabled;
  saved.recruitingCta     = cta;
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  showAutoSaved();
  if (localStorage.getItem("hb_demo_mode") !== "true") {
    _setupSave(saved);
  }
}

// ── Autosave: language ──
function autoSaveLanguage() {
  const checked = document.querySelector("input[name='content-language']:checked");
  const v = checked?.value || "english";
  localStorage.setItem("hb_lang", v);
  const saved = getSaved(); saved.languagePref = v;
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  showAutoSaved();
  if (localStorage.getItem("hb_demo_mode") !== "true") {
    _setupSave(saved);
  }
}

// ── Autosave: social handles ──
function autoSaveSocials() {
  const socials = {};
  ["linkedin","instagram","facebook","tiktok","youtube","twitter","threads","reddit","google","nextdoor","email","pinterest"].forEach(p => {
    const v = el(`social-${p}`)?.value.trim();
    if (v) socials[p] = v;
  });
  localStorage.setItem("hb_socials", JSON.stringify({ handles:socials }));
  // Also update platform handles in hb_setup
  savePlatformPrefs();
  showAutoSaved();
}

// ── Wire all profile autosave events ──
// Called from renderProfilePanel() each time the panel renders
function wireProfileAutosave() {
  const dSaveAccount  = debounce(autoSaveAccountInfo,   800);
  const dSaveIdentity = debounce(autoSaveIdentityFields, 800);
  const dSaveDisclaim = debounce(autoSaveDisclaimer,     800);
  const dSaveSocials  = debounce(autoSaveSocials,        600);

  // Account info — blur on each field
  ["profile-name","profile-brokerage","profile-email","profile-phone",
   "profile-notification-email","profile-mls-1","profile-mls-2","profile-mls-3"
  ].forEach(id => {
    const f = el(id);
    if (f) { f.removeEventListener("blur", dSaveAccount); f.addEventListener("blur", dSaveAccount); }
  });

  // SMS frequency radios — save on change
  document.querySelectorAll("input[name='sms-frequency']").forEach(r => {
    r.removeEventListener("change", dSaveAccount);
    r.addEventListener("change", dSaveAccount);
  });

  // Identity factual fields — blur
  ["business-name","market","short-bio","brand-voice","words-avoid","words-prefer",
   "audience-description",
   // Zone of Greatness — autosave on blur so values are never lost
   "origin-story","signature-perspective","unfair-advantage","not-for-client"
  ].forEach(id => {
    const f = el(id);
    if (f) { f.removeEventListener("blur", dSaveIdentity); f.addEventListener("blur", dSaveIdentity); }
  });

  // Identity selects — change
  ["setup-state"].forEach(id => {
    const f = el(id);
    if (f) { f.removeEventListener("change", autoSaveIdentityFields); f.addEventListener("change", autoSaveIdentityFields); }
  });

  // Disclaimer — blur
  const disc = el("profile-disclaimer");
  if (disc) { disc.removeEventListener("blur", dSaveDisclaim); disc.addEventListener("blur", dSaveDisclaim); }

  // Language — change
  document.querySelectorAll("input[name='content-language']").forEach(r => {
    r.removeEventListener("change", autoSaveLanguage);
    r.addEventListener("change", autoSaveLanguage);
  });

  // Social handles — blur
  document.querySelectorAll(".platform-handle-input").forEach(f => {
    f.removeEventListener("blur", dSaveSocials);
    f.addEventListener("blur", dSaveSocials);
  });
}


// Chrome ignores autocomplete="off" on many field types and autofills
// aggressively based on field name/type heuristics. This function:
// 1. Clears non-email fields that Chrome has autofilled with an email address
// 2. Runs once per panel navigation (200ms after render so autofill has fired)
// 3. One-time cleanup: removes any email address accidentally saved as a trend/niche

function clearAutofill() {
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  // Fields that should NEVER contain an email address
  const nonEmailIds = [
    "trend-input", "custom-niche-input", "audience-description",
    "market", "business-name",
    "ob-market", "ob-brokerage", "ob-mls", "ob-area-input",
    "ob-cta-url", "ob-cta-label",
    "words-avoid", "words-prefer", "short-bio", "brand-voice",
    // Zone of Greatness fields — never autofill with email
    "not-for-client", "origin-story", "signature-perspective", "unfair-advantage",
    "ob-origin-story", "ob-signature-belief", "ob-unfair-advantage", "ob-not-for",
    "intel-location-input", "idea-input",
  ];
  nonEmailIds.forEach(id => {
    const field = el(id);
    if (!field) return;
    const val = field.value || "";
    if (emailPattern.test(val.trim())) {
      field.value = "";
    }
  });

  // One-time cleanup: remove any email address that got saved into trends array
  try {
    const saved = getSaved();
    if (Array.isArray(saved.trends)) {
      const cleaned = saved.trends.filter(t => !emailPattern.test((t||"").trim()));
      if (cleaned.length !== saved.trends.length) {
        saved.trends = cleaned;
        localStorage.setItem(getSetupKey(), JSON.stringify(saved));
        _setupSave(saved);
        // Re-render trend chips if visible
        const trendDisplay = el("content-engine-trends-display");
        if (trendDisplay) {
          trendDisplay.innerHTML = cleaned.length
            ? cleaned.map(t => `<span class="chip selected">${t}</span>`).join("")
            : '<span class="empty-text">None saved yet.</span>';
        }
      }
    }
    // Also clean up any email that got saved into primaryNiches
    if (Array.isArray(saved.primaryNiches)) {
      const cleanedNiches = saved.primaryNiches.filter(n =>
        n && typeof n === "string" && !emailPattern.test(n.trim()) && !n.includes("@")
      );
      if (cleanedNiches.length !== saved.primaryNiches.length) {
        saved.primaryNiches = cleanedNiches;
        localStorage.setItem(getSetupKey(), JSON.stringify(saved));
        _setupSave(saved);
      }
    }
  } catch(e) {}
}

// Run clearAutofill once on initial load to catch any persisted bad data
document.addEventListener("DOMContentLoaded", () => setTimeout(clearAutofill, 500));


(function initAvatarDropdown() {
  const wrap = el("avatar-wrap");
  const dd   = el("avatar-dropdown");
  if (!wrap || !dd) return;

  function open() {
    updateAvatar();
    // Setup is only relevant in agent and marketing contexts
    const ctx = getViewContext();
    const setupBtn = el("dd-setup");
    if (setupBtn) setupBtn.style.display = (ctx === "agent" || ctx === "marketing") ? "" : "none";
    dd.classList.add("open");
  }
  function close(){ dd.classList.remove("open"); }

  el("sidebar-avatar-initials")?.addEventListener("click", e => { e.stopPropagation(); dd.classList.contains("open") ? close() : open(); });
  document.addEventListener("click", e => { if (wrap && !wrap.contains(e.target)) close(); });

  el("dd-setup")?.addEventListener("click",   () => { close(); navigateTo("setup-panel"); });
  el("dd-profile")?.addEventListener("click",  () => { close(); _profileFromGS = false; navigateTo("profile-panel"); });
  el("dd-billing")?.addEventListener("click",  () => { close(); _profileMode = "full"; navigateTo("profile-panel"); setTimeout(() => { const b = el("acc-body-billing"); if (b && b.style.display === "none") toggleAccordion("billing"); el("acc-billing")?.scrollIntoView({ behavior:"smooth" }); }, 200); });
  el("dd-signout")?.addEventListener("click",  () => {
    close();
    ["hb_token","hb_user","hb_view_context","hb_demo_mode"].forEach(k => localStorage.removeItem(k));
    _cachedLibrary = null;
    window.location.href = "login.html";
  });
})();

// ─────────────────────────────────────────────
// SECTION 14: GETTING STARTED CHECKLIST
// ─────────────────────────────────────────────
function gsGetState()    { return JSON.parse(localStorage.getItem("hb_gs_state") || "{}"); }
function gsSetState(upd) { localStorage.setItem("hb_gs_state", JSON.stringify({ ...gsGetState(), ...upd })); }
function gsMarkDone(n)   { gsSetState({ [`step${n}`]:true }); gsRender(); }

function gsRender() {
  const s = gsGetState();
  let done = 0;
  [1,2,3].forEach(n => {
    const stepEl  = el(`gs-step-${n}`);
    const btnEl   = el(`gs-btn-${n}`);
    if (!stepEl) return;
    const isDone   = !!s[`step${n}`];
    const isLocked = n > 1 && !s[`step${n-1}`];
    stepEl.classList.toggle("gs-done",        isDone);
    stepEl.classList.toggle("gs-step-locked", isLocked && !isDone);
    if (isDone) done++;
    if (btnEl) btnEl.textContent = isDone
      ? (n===1?"Edit Profile →":n===2?"Edit Setup →":"Generate again →")
      : (n===1?"Go to Profile →":n===2?"Go to Focus →":"Go to Content Engine →");
  });
  const bar = el("gs-progress-bar");
  if (bar) bar.style.width = Math.round((done/3)*100) + "%";

  // Show completion state when all 3 steps done
  const complete = el("gs-complete");
  const steps    = el("gs-steps");
  if (complete && steps) {
    if (done >= 3) {
      steps.style.display   = "none";
      complete.style.display = "block";
    } else {
      steps.style.display   = "flex";
      complete.style.display = "none";
    }
  }
}

function gsInjectAvatarLink() {
  const dd = el("avatar-dropdown");
  if (!dd || el("gs-avatar-link")) return;
  const link = document.createElement("a");
  link.id = "gs-avatar-link"; link.href = "#";
  link.style.cssText = "display:flex;align-items:center;gap:8px;padding:10px 16px;font-size:13px;color:var(--ink-2);text-decoration:none;border-bottom:1px solid var(--border);";
  link.innerHTML = `<span>🚀</span> Getting Started`;
  link.onclick = e => { e.preventDefault(); el("avatar-dropdown")?.classList.remove("open"); navigateTo("getting-started-panel"); gsRender(); };
  dd.insertBefore(link, dd.firstChild);
}

// GS nav buttons wired via delegated click
document.addEventListener("click", e => {
  const btn = e.target.closest("[data-gs-panel]");
  if (btn) navigateTo(btn.dataset.gsPanel);
});

// ─────────────────────────────────────────────
// ─────────────────────────────────────────────
// SECTION 11B: ONBOARDING FLOW
// ─────────────────────────────────────────────
// Five-block first-time onboarding replacing the old Getting Started checklist.
// Routing: _bootAsAgent() sends new users here. Returning users go straight to
// content-engine-panel. All data saves to the same endpoints as Profile + Setup.

let obCurrentBlock = 1;
const OB_TOTAL     = 5;
const OB_LABELS    = ["Foundation", "Who you serve", "Your voice", "Market & reach", "Your first post"];

function obInit() {
  const saved = getSaved();
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");
  // Pre-fill Block 1
  if (el("ob-name"))      el("ob-name").value      = user?.agent_name || saved.agentName || "";
  if (el("ob-brokerage")) el("ob-brokerage").value = user?.brokerage  || saved.brokerage  || "";
  if (el("ob-market"))    el("ob-market").value    = saved.market     || "";
  if (el("ob-state"))     el("ob-state").value     = saved.state      || "";
  const hbMls = JSON.parse(localStorage.getItem("hb_mls") || "[]");
  if (el("ob-mls"))       el("ob-mls").value       = hbMls[0]         || "";
  // Pre-fill Block 3
  if (el("ob-origin-story"))  el("ob-origin-story").value  = saved.originStory          || "";
  if (el("ob-sig-belief"))    el("ob-sig-belief").value    = saved.signaturePerspective  || "";
  if (el("ob-unfair-adv"))    el("ob-unfair-adv").value    = saved.unfairAdvantage       || "";
  if (el("ob-not-for"))       el("ob-not-for").value       = saved.notForClient          || "";
  // Pre-fill Block 4
  if (el("ob-cta-type"))  el("ob-cta-type").value  = saved.ctaType   || "";
  if (el("ob-cta-url"))   el("ob-cta-url").value   = saved.ctaUrl    || "";
  if (el("ob-cta-label")) el("ob-cta-label").value = saved.ctaLabel  || "";
  if (el("ob-audience"))  el("ob-audience").value  = saved.audienceDescription || "";
  // Render niche UI for Block 2
  obActiveCategoryFilter = null;
  obRenderNiches();
  // Render service areas for Block 4
  obRenderServiceAreas();
  // Wire signature belief second-pass nudge
  const sigField = el("ob-sig-belief");
  if (sigField) {
    sigField.removeEventListener("blur",  obCheckSignatureBelief);
    sigField.removeEventListener("input", obClearSigNudge);
    sigField.addEventListener("blur",  obCheckSignatureBelief);
    sigField.addEventListener("input", obClearSigNudge);
  }
  // Start at first incomplete block, or block 1
  obCurrentBlock = obFirstIncompleteBlock();
  obRenderStepper();
  obRenderBlock(obCurrentBlock);
}

function obClearSigNudge() {
  const nudge = el("ob-sig-nudge");
  if (nudge) nudge.style.display = "none";
}

function obFirstIncompleteBlock() {
  const saved = getSaved();
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!(user?.agent_name || saved.agentName) || !saved.market) return 1;
  if (!(Array.isArray(saved.primaryNiches) && saved.primaryNiches.length)) return 2;
  if (!saved.originStory || !saved.signaturePerspective) return 3;
  if (!saved.ctaUrl) return 4;
  return 1;
}

function obRenderStepper() {
  const stepper = el("ob-stepper"); if (!stepper) return;
  let html = "";
  OB_LABELS.forEach((label, idx) => {
    const n = idx + 1;
    const isDone   = n < obCurrentBlock;
    const isActive = n === obCurrentBlock;
    const dotCls   = isDone ? "ob-dot done" : isActive ? "ob-dot active" : "ob-dot";
    const inner    = isDone ? "&#10003;" : String(n);
    const lblCls   = isActive ? "ob-dot-label active" : "ob-dot-label";
    if (idx > 0) html += '<div style="flex:1;height:1px;background:var(--border);margin-top:14px;"></div>';
    html += `<div class="ob-dot-wrap">
      <div class="${dotCls}">${inner}</div>
      <div class="${lblCls}">${label}</div>
    </div>`;
  });
  stepper.innerHTML = html;
}

function obRenderBlock(n) {
  for (let i = 1; i <= OB_TOTAL; i++) {
    const b = el("ob-block-" + i);
    if (b) b.style.display = i === n ? "block" : "none";
  }
  const backBtn  = el("ob-back-btn");
  const nextBtn  = el("ob-next-btn");
  const progress = el("ob-progress");
  if (backBtn)  backBtn.style.visibility = n === 1 ? "hidden" : "visible";
  if (progress) progress.textContent     = n + " of " + OB_TOTAL;
  if (nextBtn) {
    nextBtn.style.background = "";
    if (n === 4)        { nextBtn.textContent = "Generate my first post →"; }
    else if (n === OB_TOTAL) { nextBtn.textContent = "Go to my content →"; nextBtn.style.background = "var(--green)"; }
    else                { nextBtn.textContent = "Save and continue →"; }
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function obCheckSignatureBelief() {
  const field = el("ob-sig-belief"); if (!field) return;
  const val   = field.value.trim();
  if (!val || val.length < 10) return;
  const nudge = el("ob-sig-nudge"); if (!nudge) return;
  // Heuristics: no numbers, short, contains only generic virtue words
  const hasNumber      = /\d/.test(val);
  const isLong         = val.length > 80;
  const genericTerms   = ["honest","integrity","hard work","client first","passion","dedicated","committed","trust","transparency","communication"];
  const isGenericOnly  = !hasNumber && !isLong && genericTerms.some(t => val.toLowerCase().includes(t));
  const lacksSpecifics = !hasNumber && val.length < 70;
  nudge.style.display = (isGenericOnly || lacksSpecifics) ? "block" : "none";
}

async function obSaveBlock(n) {
  const saved = getSaved();
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");

  if (n === 1) {
    const name      = el("ob-name")?.value.trim()      || "";
    const brokerage = el("ob-brokerage")?.value.trim() || "";
    const market    = el("ob-market")?.value.trim()    || "";
    const state     = el("ob-state")?.value            || "";
    const mls       = el("ob-mls")?.value.trim()       || "";
    if (!name)   { showToast("Please enter your name to continue."); el("ob-name")?.focus(); return false; }
    if (!market) { showToast("Please enter your primary market city."); el("ob-market")?.focus(); return false; }
    saved.agentName = name; saved.brokerage = brokerage;
    saved.market = market; saved.state = state;
    if (user) { user.agent_name = name; user.brokerage = brokerage; localStorage.setItem("hb_user", JSON.stringify(user)); }
    if (mls) localStorage.setItem("hb_mls", JSON.stringify([mls]));
    localStorage.setItem("hb_setup", JSON.stringify(saved));
    updateAvatar();
    authFetch(`${BACKEND_URL}/auth/profile`, { method:"POST", body:JSON.stringify({ agent_name:name, brokerage, email:user?.email||"", phone:user?.phone||"" }) }).catch(()=>{});
    _setupSave(saved);
    return true;
  }

  if (n === 2) {
    if (!selectedPrimaryNiches.length) { showToast("Please select at least one niche to continue."); return false; }
    saved.primaryNiches       = selectedPrimaryNiches;
    saved.subNiches           = selectedSubNiches;
    saved.audienceDescription = el("ob-audience")?.value.trim()      || saved.audienceDescription || "";
    saved.recentClientStory   = el("ob-client-story")?.value.trim()  || "";
    localStorage.setItem("hb_setup", JSON.stringify(saved));
    _setupSave(saved);
    return true;
  }

  if (n === 3) {
    const origin = el("ob-origin-story")?.value.trim() || "";
    const sigBel = el("ob-sig-belief")?.value.trim()   || "";
    if (!origin) { showToast("Please tell us why you got into real estate — this shapes every post."); el("ob-origin-story")?.focus(); return false; }
    if (!sigBel) { showToast("Please share your signature belief — this is the heart of your voice."); el("ob-sig-belief")?.focus(); return false; }
    saved.originStory          = origin;
    saved.signaturePerspective = sigBel;
    saved.unfairAdvantage      = el("ob-unfair-adv")?.value.trim() || "";
    saved.notForClient         = el("ob-not-for")?.value.trim()    || "";
    localStorage.setItem("hb_setup", JSON.stringify(saved));
    _setupSave(saved);
    return true;
  }

  if (n === 4) {
    const ctaUrl   = el("ob-cta-url")?.value.trim()  || "";
    const ctaType  = el("ob-cta-type")?.value         || "";
    const ctaLabel = el("ob-cta-label")?.value.trim() || "";
    const areas    = obGetServiceAreas();
    saved.ctaUrl = ctaUrl; saved.ctaType = ctaType; saved.ctaLabel = ctaLabel;
    saved.serviceAreas = areas;
    localStorage.setItem("hb_setup", JSON.stringify(saved));
    _setupSave(saved);
    // Fire generation — awaited so block 5 shows loading state immediately
    obGeneratePreview();
    return true;
  }

  return true;
}

async function obNext() {
  if (obCurrentBlock === OB_TOTAL) {
    navigateTo("content-engine-panel");
    return;
  }
  const nextBtn = el("ob-next-btn");
  if (nextBtn) { nextBtn.disabled = true; nextBtn.textContent = "Saving…"; }
  const ok = await obSaveBlock(obCurrentBlock);
  if (nextBtn) { nextBtn.disabled = false; }
  if (!ok) { obRenderBlock(obCurrentBlock); return; }
  obCurrentBlock++;
  obRenderStepper();
  obRenderBlock(obCurrentBlock);
}

function obBack() {
  if (obCurrentBlock <= 1) return;
  obCurrentBlock--;
  obRenderStepper();
  obRenderBlock(obCurrentBlock);
}

// ── Niche rendering for Block 2 ──
let obActiveCategoryFilter = null;

function obRenderNiches() {
  // Selected chips bar
  const selEl = el("ob-niche-selected");
  if (selEl) {
    if (selectedPrimaryNiches.length) {
      selEl.style.display = "flex";
      selEl.innerHTML = selectedPrimaryNiches.map(n =>
        `<div class="chip selected" onclick="obRemoveNiche(${JSON.stringify(n)})">${n} <span class="chip-remove">&#10005;</span></div>`
      ).join("");
    } else {
      selEl.style.display = "none";
      selEl.innerHTML = "";
    }
  }
  // Category tabs
  const tabsEl = el("ob-niche-tabs");
  if (tabsEl) {
    tabsEl.innerHTML = Object.keys(NICHE_CATEGORIES).map(cat => {
      const isActive = obActiveCategoryFilter === cat;
      return `<div class="chip${isActive ? " selected" : ""}" style="${isActive ? "background:var(--ink);color:#fff;border-color:var(--ink);font-weight:600;" : ""}" onclick="obSetCategory(${JSON.stringify(cat)})">${cat}</div>`;
    }).join("");
  }
  // Niche options for active category
  const optsEl = el("ob-niche-options");
  if (optsEl) {
    optsEl.innerHTML = "";
    if (!obActiveCategoryFilter) {
      optsEl.innerHTML = '<div style="font-size:13px;color:var(--ink-3);font-style:italic;padding:4px 0;">Select a category above to browse niches.</div>';
      return;
    }
    const nichesToShow = NICHE_CATEGORIES[obActiveCategoryFilter] || [];
    nichesToShow.forEach(niche => {
      const chip = document.createElement("div");
      chip.className = "chip" + (selectedPrimaryNiches.includes(niche) ? " selected" : "");
      chip.textContent = niche;
      chip.addEventListener("click", () => {
        if (selectedPrimaryNiches.includes(niche)) {
          selectedPrimaryNiches = selectedPrimaryNiches.filter(n => n !== niche);
          selectedSubNiches = selectedSubNiches.filter(s => !(NICHE_DATA[niche]||[]).includes(s));
        } else {
          selectedPrimaryNiches.push(niche);
          // Auto-add first 3 sub-niches so profile is immediately richer
          (NICHE_DATA[niche]||[]).slice(0,3).forEach(s => { if (!selectedSubNiches.includes(s)) selectedSubNiches.push(s); });
        }
        obRenderNiches();
      });
      optsEl.appendChild(chip);
    });
  }
}

function obSetCategory(cat) {
  obActiveCategoryFilter = (obActiveCategoryFilter === cat) ? null : cat;
  obRenderNiches();
}

function obRemoveNiche(niche) {
  selectedPrimaryNiches = selectedPrimaryNiches.filter(n => n !== niche);
  selectedSubNiches = selectedSubNiches.filter(s => !(NICHE_DATA[niche]||[]).includes(s));
  obRenderNiches();
}

// ── Service areas for Block 4 ──
let _obServiceAreas = [];

function obRenderServiceAreas() {
  const saved = getSaved();
  _obServiceAreas = Array.isArray(saved.serviceAreas) ? [...saved.serviceAreas] : [];
  obRefreshAreaChips();
}

function obRefreshAreaChips() {
  const container = el("ob-area-chips"); if (!container) return;
  const hint      = el("ob-area-hint");
  container.innerHTML = _obServiceAreas.map(a =>
    `<div class="chip selected">${a} <span class="chip-remove" onclick="obRemoveArea(${JSON.stringify(a)})">&#10005;</span></div>`
  ).join("");
  if (hint) hint.style.display = _obServiceAreas.length >= 5 ? "block" : "none";
}

function obAddArea() {
  const input = el("ob-area-input"); if (!input) return;
  const v = input.value.trim(); if (!v) return;
  if (_obServiceAreas.length >= 5) { showToast("Maximum 5 service areas reached."); return; }
  if (!_obServiceAreas.includes(v)) _obServiceAreas.push(v);
  obRefreshAreaChips();
  input.value = "";
  input.focus();
}

function obRemoveArea(area) {
  _obServiceAreas = _obServiceAreas.filter(a => a !== area);
  obRefreshAreaChips();
}

function obGetServiceAreas() { return _obServiceAreas; }

// ── Preview generation for Block 5 ──
async function obGeneratePreview() {
  const saved     = getSaved();
  const user      = JSON.parse(localStorage.getItem("hb_user") || "null");
  const hbMls     = JSON.parse(localStorage.getItem("hb_mls") || "[]");
  const loadEl    = el("ob-preview-loading");
  const areaEl    = el("ob-preview-area");
  const postEl    = el("ob-preview-post");
  const errEl     = el("ob-preview-error");
  if (loadEl) loadEl.style.display = "block";
  if (areaEl) areaEl.style.display = "none";
  if (postEl) postEl.style.display = "none";
  if (errEl)  errEl.style.display  = "none";
  const primaryNiche = (saved.primaryNiches||[])[0] || "Residential Buying & Selling";
  const situation    = "Spring market — what buyers and sellers need to know right now";
  const serviceAreas = obGetServiceAreas().length ? obGetServiceAreas() : (saved.serviceAreas||[]);
  const payload = {
    identity:    { primaryCategories:[primaryNiche], subNichesByCategory:{}, trendPreferences:[] },
    agentProfile:{
      agentName:           saved.agentName || user?.agent_name || "",
      businessName:        saved.businessName || "",
      brokerage:           saved.brokerage || user?.brokerage || "",
      market:              getMarketContext(),
      brandVoice:          saved.brandVoice || "",
      shortBio:            saved.shortBio   || "",
      audienceDescription: saved.audienceDescription || "",
      wordsAvoid:          saved.wordsAvoid  || "",
      wordsPrefer:         saved.wordsPrefer || "",
      mlsNames:            hbMls,
      serviceAreas:        serviceAreas,
      designations:        saved.designations || [],
      languagePref:        "english",
      state:               saved.state || "",
      ctaMethods:          getCtaMethods(),
      ctaType:             (getCtaMethods()[0]||{}).type  || "",
      ctaUrl:              (getCtaMethods()[0]||{}).url   || "",
      ctaLabel:            (getCtaMethods()[0]||{}).label || "",
      mlsData:             "",
      originStory:         saved.originStory          || "",
      unfairAdvantage:     saved.unfairAdvantage      || "",
      signaturePerspective:saved.signaturePerspective || "",
      notForClient:        saved.notForClient         || "",
      recentClientStory:   saved.recentClientStory    || "",
    },
    situation, persona:null, tone:null, length:"medium",
    content_mode: "agent",
  };
  try {
    const res  = await authFetch(`${BACKEND_URL}/content/generate-content`, { method:"POST", body:JSON.stringify(payload) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Generation failed");
    const content = data.content || {};
    // Save to library as pending — available immediately in My Content
    try {
      const libRes = await authFetch(`${BACKEND_URL}/library`, {
        method:"POST",
        body: JSON.stringify({ niche:primaryNiche, content, compliance:data.compliance||{}, context:"agent" })
      });
      const libData = await libRes.json();
      window._obLibraryItemId = libData.id || null;
    } catch(e) { window._obLibraryItemId = null; }
    window._obGeneratedData = data;
    // Render preview
    if (loadEl) loadEl.style.display = "none";
    if (areaEl) areaEl.style.display = "block";
    if (postEl) {
      postEl.style.display = "block";
      const compliance  = data.compliance || {};
      const verdict     = compliance.overall_verdict || compliance.overallStatus || "pass";
      const vColor      = verdict === "pass" ? "var(--green)" : verdict === "review" ? "var(--amber)" : "var(--red)";
      const vLabel      = verdict === "pass" ? "&#10003; Compliance pass" : verdict === "review" ? "&#9888; Review recommended" : "&#10005; Compliance check required";
      const headline    = content.headline || "";
      const post        = content.post      || "";
      const cta         = content.cta       || "";
      postEl.innerHTML  = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
          <span style="font-size:11px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:${vColor};">${vLabel}</span>
          <span style="font-size:11px;color:var(--ink-4);">CIR&#8482; created on approval</span>
        </div>
        ${headline ? `<div style="font-size:17px;font-weight:700;letter-spacing:-0.01em;color:var(--ink);margin-bottom:14px;line-height:1.3;">${headline}</div>` : ""}
        <div style="font-size:14px;line-height:1.8;color:var(--ink);white-space:pre-wrap;margin-bottom:12px;">${post}</div>
        ${cta ? `<div style="font-size:13px;font-weight:600;color:var(--blue);border-top:1px solid var(--border);padding-top:12px;">${cta}</div>` : ""}
      `;
    }
  } catch(e) {
    if (loadEl) loadEl.style.display = "none";
    if (areaEl) areaEl.style.display = "block";
    if (errEl) {
      errEl.style.display  = "block";
      errEl.textContent    = "Could not generate your preview — your profile is saved. Continue to the app and generate from the Content Engine.";
    }
  }
}

async function obApproveAndGo() {
  const btn = el("ob-approve-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Approving…"; }
  try {
    const itemId = window._obLibraryItemId;
    if (itemId) {
      await authFetch(`${BACKEND_URL}/library/${itemId}`, {
        method:"PATCH", body:JSON.stringify({ status:"approved" })
      });
    }
  } catch(e) {}
  navigateTo("library-panel");
}

// SECTION 14B: PLATFORM OAUTH CONNECTIONS
// ─────────────────────────────────────────────

// Platforms that support direct OAuth connection
const OAUTH_PLATFORMS = ["linkedin", "google", "facebook"];

// Connect a platform via OAuth
function connectPlatform(platform) {
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  if (isDemo) {
    showToast("Demo mode — platform connection simulated.");
    setConnectedState(platform, "demo-user");
    return;
  }
  const token = localStorage.getItem("hb_token");
  if (!token) { showToast("Please log in first."); return; }
  // Set connecting state
  const btn = document.getElementById("plat-btn-" + platform);
  if (btn) { btn.textContent = "Connecting…"; btn.classList.add("connecting"); btn.disabled = true; }
  // Store token in sessionStorage so backend can read it via state param after OAuth dance
  // Backend /connect endpoint reads token from Authorization header via a pre-auth fetch
  // We make a fetch first to get the redirect URL, then redirect the browser
  authFetch(BACKEND_URL + "/social/" + platform + "/connect")
    .then(res => {
      if (res.status === 401) { showToast("Session expired. Please log in again."); return; }
      return res.json();
    })
    .then(data => {
      if (data && data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        if (btn) { btn.textContent = "Connect " + platform.charAt(0).toUpperCase() + platform.slice(1) + " →"; btn.classList.remove("connecting"); btn.disabled = false; }
        showToast("Could not start connection. Please try again.");
      }
    })
    .catch(() => {
      if (btn) { btn.textContent = "Connect " + platform.charAt(0).toUpperCase() + platform.slice(1) + " →"; btn.classList.remove("connecting"); btn.disabled = false; }
      showToast("Connection failed. Check your internet and try again.");
    });
}

// Disconnect a platform
async function disconnectPlatform(platform) {
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  if (isDemo) { clearConnectedState(platform); return; }
  try {
    await authFetch(BACKEND_URL + "/social/" + platform + "/disconnect", { method: "POST" });
  } catch(e) {}
  clearConnectedState(platform);
}

// Set a platform to "connected" state in the UI
function setConnectedState(platform, username) {
  const btn    = document.getElementById("plat-btn-" + platform);
  const status = document.getElementById("plat-status-" + platform);
  if (btn) {
    btn.textContent = "✓ Connected";
    btn.classList.remove("connecting");
    btn.classList.add("connected");
    btn.disabled = true;
    btn.onclick = null;
  }
  if (status) {
    status.innerHTML = "";
    status.style.display = "flex";
    status.style.alignItems = "center";
    status.style.gap = "8px";
    const disconnectBtn = document.createElement("button");
    disconnectBtn.className = "plat-disconnect-link";
    disconnectBtn.textContent = "Disconnect";
    disconnectBtn.addEventListener("click", () => disconnectPlatform(platform));
    if (username && username !== "demo-user") {
      const nameSpan = document.createElement("span");
      nameSpan.textContent = username + " ";
      status.appendChild(nameSpan);
    }
    status.appendChild(disconnectBtn);
  }
  // Also mark the handle row visible so they can add their handle
  const handleWrap = document.getElementById("plat-handle-wrap-" + platform);
  if (handleWrap) handleWrap.style.display = "flex";
  // Store in localStorage for quick access
  const connections = JSON.parse(localStorage.getItem("hb_oauth_connections") || "{}");
  connections[platform] = { connected: true, username: username || "", connectedAt: new Date().toISOString() };
  localStorage.setItem("hb_oauth_connections", JSON.stringify(connections));
}

// Clear connected state
function clearConnectedState(platform) {
  const btn    = document.getElementById("plat-btn-" + platform);
  const status = document.getElementById("plat-status-" + platform);
  if (btn) {
    const labels = { linkedin: "Connect LinkedIn →", google: "Connect Google →", facebook: "Connect Facebook →" };
    btn.textContent = labels[platform] || "Connect →";
    btn.classList.remove("connected", "connecting");
    btn.disabled = false;
    btn.onclick = function() { connectPlatform(platform); };
  }
  if (status) { status.style.display = "none"; status.innerHTML = ""; }
  const connections = JSON.parse(localStorage.getItem("hb_oauth_connections") || "{}");
  delete connections[platform];
  localStorage.setItem("hb_oauth_connections", JSON.stringify(connections));
}

// Load connection status from backend + update UI
async function loadPlatformConnections() {
  // First apply any cached connections from localStorage
  const cached = JSON.parse(localStorage.getItem("hb_oauth_connections") || "{}");
  Object.entries(cached).forEach(([platform, data]) => {
    if (data.connected) setConnectedState(platform, data.username);
  });

  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  if (isDemo) return;

  try {
    const res = await authFetch(BACKEND_URL + "/social/connections");
    if (!res.ok) return;
    const data = await res.json();
    const connections = data.connections || [];
    // Only clear and rebuild if the backend returned a valid response
    // (even if connections array is empty — that's a valid "nothing connected" state)
    if (!Array.isArray(data.connections)) return;
    // Clear all OAuth platform states first
    OAUTH_PLATFORMS.forEach(p => clearConnectedState(p));
    localStorage.removeItem("hb_oauth_connections");
    // Set connected state for each confirmed connection
    connections.forEach(conn => {
      setConnectedState(conn.platform, conn.handle || "");
    });
    // B-24: Show page prompt if Facebook is connected but no page token stored
    const fbConn = connections.find(c => c.platform === "facebook");
    const prompt = document.getElementById("fb-page-prompt");
    if (prompt) {
      if (fbConn && !fbConn.has_page_token) {
        prompt.style.display = "flex";
      } else {
        prompt.style.display = "none";
      }
    }
  } catch(e) {}
}

// Check URL for OAuth callback (?connected=linkedin or ?error=... or ?select_page=facebook)
function checkOAuthCallback() {
  const params = new URLSearchParams(window.location.search);
  const connected   = params.get("connected");
  const selectPage  = params.get("select_page");
  const pagesParam  = params.get("pages");
  const oauthError  = params.get("oauth_error");

  // Facebook page picker flow — show page selection modal before marking connected
  if (selectPage === "facebook" && pagesParam) {
    window.history.replaceState({}, "", window.location.pathname);
    const user = JSON.parse(localStorage.getItem("hb_user") || "null");
    if (user && (user.role === "super_admin" || user.role === "admin")) {
      window._bootViewOverride = true;
      setViewContext("agent");
      renderNav("agent");
    }
    navigateTo("profile-panel");
    setTimeout(() => {
      const body = document.getElementById("acc-body-platforms");
      if (body && body.style.display === "none") toggleAccordion("platforms");
      try {
        const pages = JSON.parse(decodeURIComponent(pagesParam));
        showFbPagePicker(pages);
      } catch(e) {
        showToast("Facebook connected — but could not load page list. Please try reconnecting.");
      }
    }, 400);
    return;
  }

  if (connected) {
    window.history.replaceState({}, "", window.location.pathname);
    // Ensure we are in agent (My Work) context before navigating to profile panel
    // Set _bootViewOverride so bootForRole does not reset context back to admin/super_admin
    const user = JSON.parse(localStorage.getItem("hb_user") || "null");
    if (user && (user.role === "super_admin" || user.role === "admin")) {
      window._bootViewOverride = true;
      setViewContext("agent");
      renderNav("agent");
    }
    navigateTo("profile-panel");
    setTimeout(() => {
      const body = document.getElementById("acc-body-platforms");
      if (body && body.style.display === "none") toggleAccordion("platforms");
      // Reload connections from backend
      loadPlatformConnections().then(() => {
        showToast("✓ " + connected.charAt(0).toUpperCase() + connected.slice(1) + " connected successfully");
      });
    }, 400);
  }
  if (oauthError) {
    window.history.replaceState({}, "", window.location.pathname);
    const user = JSON.parse(localStorage.getItem("hb_user") || "null");
    if (user && (user.role === "super_admin" || user.role === "admin")) {
      window._bootViewOverride = true;
      setViewContext("agent");
      renderNav("agent");
    }
    navigateTo("profile-panel");
    setTimeout(() => {
      const body = document.getElementById("acc-body-platforms");
      if (body && body.style.display === "none") toggleAccordion("platforms");
      showToast("Connection failed — " + decodeURIComponent(oauthError).replace(/\+/g, " "));
    }, 400);
  }
}

// Show Facebook page picker modal
function showFbPagePicker(pages) {
  const modal = document.getElementById("fb-page-picker-modal");
  const list  = document.getElementById("fb-page-picker-list");
  if (!modal || !list) return;
  list.innerHTML = "";
  if (!pages || pages.length === 0) {
    list.innerHTML = '<div style="font-size:13px;color:var(--ink-3);padding:8px 0;">No Facebook Pages found for this account. Make sure you are connected to the account that manages your business page.</div>';
  } else {
    pages.forEach(page => {
      const card = document.createElement("div");
      card.style.cssText = "padding:14px 16px;border:1.5px solid var(--border);border-radius:12px;cursor:pointer;display:flex;align-items:center;gap:12px;transition:border-color 0.15s,background 0.15s;";
      card.innerHTML = '<div style="width:36px;height:36px;border-radius:8px;background:var(--blue-dim);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:var(--blue);flex-shrink:0;">f</div>'
        + '<div style="flex:1;"><div style="font-size:14px;font-weight:600;color:var(--ink);">' + page.name + '</div>'
        + '<div style="font-size:11px;color:var(--ink-3);margin-top:2px;">Facebook Page</div></div>'
        + '<div style="font-size:12px;color:var(--blue);font-weight:600;">Select →</div>';
      card.addEventListener("mouseenter", () => { card.style.borderColor = "var(--blue)"; card.style.background = "var(--blue-dim)"; });
      card.addEventListener("mouseleave", () => { card.style.borderColor = "var(--border)"; card.style.background = ""; });
      card.addEventListener("click", () => selectFbPage(page.id, page.name, page.access_token));
      list.appendChild(card);
    });
  }
  modal.style.display = "flex";
}

// Called when agent selects a page from the picker
async function selectFbPage(pageId, pageName, pageToken) {
  const modal = document.getElementById("fb-page-picker-modal");
  if (modal) modal.style.display = "none";
  try {
    const r = await authFetch(BACKEND_URL + "/social/facebook/select-page", {
      method: "POST",
      body: JSON.stringify({ page_id: pageId, page_name: pageName, page_token: pageToken })
    });
    if (!r.ok) throw new Error();
    loadPlatformConnections().then(() => {
      showToast("✓ Facebook connected — posting to " + pageName);
    });
  } catch(e) {
    showToast("Could not save page selection. Please try reconnecting Facebook.");
  }
}

// Close the page picker without selecting
function closeFbPagePicker() {
  const modal = document.getElementById("fb-page-picker-modal");
  if (modal) modal.style.display = "none";
}

// B-24: Trigger page picker from the in-panel prompt button
// Fetches available pages live from the backend then shows the picker modal
async function triggerFbPagePicker() {
  try {
    const res  = await authFetch(BACKEND_URL + "/social/facebook/page-token");
    if (!res.ok) throw new Error();
    const data = await res.json();
    const pages = data.pages || [];
    if (!pages.length) {
      showToast("No Facebook Pages found. Make sure you are connected to the account that manages your business page.");
      return;
    }
    showFbPagePicker(pages);
  } catch(e) {
    showToast("Could not load your Facebook Pages. Try disconnecting and reconnecting Facebook.");
  }
}

// Show a floating toast message
function showToast(message) {
  const existing = document.getElementById("hb-toast");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.id = "hb-toast";
  toast.style.cssText = "position:fixed;bottom:32px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;padding:12px 28px;border-radius:999px;font-size:14px;font-weight:500;font-family:inherit;z-index:9999;letter-spacing:-0.01em;white-space:nowrap;pointer-events:none;animation:fadeInUp 0.3s ease;";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ─────────────────────────────────────────────
// SECTION 15: RESULTS PANEL
// ─────────────────────────────────────────────
async function loadResults() {
  try {
    let d;
    if (localStorage.getItem("hb_demo_mode") === "true") {
      const lib = window._demoLibrary || [];
      // Build live stats from actual demo library — reflects what user has done this session
      const niches = {};
      lib.forEach(x => { const n = x.niche||"General"; niches[n] = niches[n]||{total:0,published:0}; niches[n].total++; if (x.status==="published") niches[n].published++; });
      const passing = lib.filter(x => { const v = x.compliance?.overallStatus||x.compliance?.overall_verdict||""; return v==="pass"||v==="compliant"; }).length;
      const reviewed = lib.filter(x => x.status==="approved"||x.status==="published").length;
      const platforms = [...new Set(lib.filter(x=>x.platform).map(x=>x.platform))];
      d = {
        total_published:   lib.filter(x=>x.status==="published").length,
        total_pending:     lib.filter(x=>x.status==="pending").length,
        total_generated:   lib.length,
        platforms_reached: platforms.length || 3,
        this_month:        lib.length,
        active_schedules:  2,
        compliance_rate:   reviewed > 0 ? Math.round((passing/reviewed)*100) : 100,
        platform_list:     platforms.length ? platforms.map(p=>p.charAt(0).toUpperCase()+p.slice(1)) : ["Instagram","LinkedIn","Facebook"],
        niche_breakdown:   Object.entries(niches).map(([niche,v])=>({niche,...v})),
      };
    } else {
      const res = await authFetch(`${BACKEND_URL}/results`);
      if (!res.ok) return;
      d = await res.json();
    }
    set("results-published",  d.total_published  ?? "—");
    set("results-platforms",  d.platforms_reached ?? "—");
    set("results-pending",    d.total_pending    ?? "—");
    set("results-generated",  d.total_generated  ?? "—");
    set("results-this-month", d.this_month       ?? "—");
    set("results-schedules",  d.active_schedules ?? "—");

    const compEl = el("results-compliance");
    if (compEl) {
      if (d.compliance_rate == null) { compEl.textContent = "—"; }
      else {
        compEl.textContent = d.compliance_rate + "%";
        compEl.style.color = d.compliance_rate >= 90 ? "var(--green)" : d.compliance_rate >= 70 ? "var(--amber)" : "var(--red)";
      }
    }
    const platList = el("results-platform-list");
    if (platList && d.platform_list?.length) platList.textContent = d.platform_list.join(", ");

    const breakdown = el("results-niche-breakdown");
    if (breakdown) {
      if (!d.niche_breakdown?.length) {
        breakdown.innerHTML = '<div style="font-size:13px;color:var(--muted);font-style:italic;">No content yet. Generate your first piece to start tracking.</div>';
      } else {
        const maxTotal = Math.max(...d.niche_breakdown.map(n=>n.total));
        breakdown.innerHTML = d.niche_breakdown.map(n => {
          const pct = maxTotal > 0 ? Math.round((n.total/maxTotal)*100) : 0;
          return `<div style="margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
              <span style="font-size:13px;font-weight:600;">${n.niche}</span>
              <span style="font-size:12px;color:var(--muted);">${n.total} generated · ${n.published} published</span>
            </div>
            <div style="background:var(--surface);border-radius:4px;height:6px;">
              <div style="background:var(--blue);border-radius:4px;height:6px;width:${pct}%;transition:width .4s;"></div>
            </div></div>`;
        }).join("");
      }
    }
  } catch(e) { console.warn("Results load error:", e); }
}

// ─────────────────────────────────────────────
// SECTION 16: IDENTITY SCORE
// ─────────────────────────────────────────────
const SCORE_LEVELS = [
  { min:90, label:"Verified",       next:null,           color:"var(--green)" },
  { min:75, label:"Trusted",        next:"Verified",     threshold:90,  color:"var(--blue)" },
  { min:50, label:"Established",    next:"Trusted",      threshold:75,  color:"var(--blue)" },
  { min:30, label:"Building",       next:"Established",  threshold:50,  color:"var(--amber)" },
  { min:0,  label:"Getting Started",next:"Building",     threshold:30,  color:"var(--muted)" },
];
function getScoreLevel(n) { return SCORE_LEVELS.find(l=>n>=l.min) || SCORE_LEVELS[SCORE_LEVELS.length-1]; }

// ─────────────────────────────────────────────
// JORDAN IDENTITY CARD
// Replaces the old score widget on the Identity page.
// Jordan speaks in plain language about what the team
// has accomplished and what is working for the agent.
//
// Jordan's message is generated by the Claude API so it
// reflects the agent's chosen character brief and name.
// Results are cached in localStorage under hb_jordan_card_cache.
// Cache invalidates only when meaningful data changes:
//   CIR tier / schedule active / platforms count / Jordan name or brief
//
// FUTURE NOTE FOR DEVELOPERS:
// At scale (40-50+ agents), move Jordan message generation to the
// backend — a dedicated /jordan/identity-brief endpoint — so API keys
// are never exposed client-side and caching is handled per user.
// ─────────────────────────────────────────────

function _jordanCirTier(n) {
  if (n === 0)  return "none";
  if (n < 10)   return "starting";
  if (n < 50)   return "growing";
  return "established";
}

function _jordanCacheKey(data) {
  const { cir_count, schedule_active, platforms_connected, identity_complete } = data;
  const name  = jordanName();
  const brief = jordanBrief();
  const tier  = _jordanCirTier(cir_count);
  return [tier, schedule_active ? 1 : 0, platforms_connected, identity_complete ? 1 : 0, name, brief].join("|");
}

function _jordanFallbackMessage(data) {
  const { cir_count, identity_complete } = data;
  const name = jordanName();
  if (!identity_complete) {
    return name + " here. Your profile is not fully filled in yet. Once you add your voice, your market, and your niches, your whole team will know exactly how to work for you.";
  }
  if (cir_count === 0) {
    return "Your profile is all set and your team knows what to do. Approve your first post and you will have your first verified record on file. That is when your name really starts to get out there.";
  }
  if (cir_count < 10) {
    return "You are off to a good start. Your team has " + cir_count + " verified post" + (cir_count === 1 ? "" : "s") + " on file, each one helping the right people find you. Keep going.";
  }
  if (cir_count < 50) {
    return cir_count + " posts are out there right now showing up in searches and building your name. Your Writer knows how you talk, your Analyst is watching your market, and your Auditor makes sure everything going out looks professional.";
  }
  return cir_count + " posts. That is " + cir_count + " times your name showed up somewhere online when someone needed answers. Your whole team has been working hard for you and it shows. Keep approving content and that number keeps climbing.";
}

async function _jordanGenerateMessage(data) {
  // Check cache first — only generate when something meaningful changed
  const cacheKey = _jordanCacheKey(data);
  try {
    const cached = JSON.parse(localStorage.getItem("hb_jordan_card_cache") || "{}");
    if (cached.key === cacheKey && cached.message) {
      return cached.message;
    }
  } catch(e) {}

  const { cir_count, schedule_active, platforms_connected, identity_complete } = data;
  const name  = jordanName();
  const brief = jordanBrief();

  // Message generation routes through backend — API key never exposed client-side.
  // System prompt and user prompt are built server-side in POST /jordan/message.
  try {
    const res = await authFetch(`${BACKEND_URL}/jordan/message`, {
      method: "POST",
      body: JSON.stringify({
        type:         "identity",
        data:         { cir_count, schedule_active, platforms_connected, identity_complete },
        jordan_name:  name,
        jordan_brief: brief,
      }),
    });

    if (!res.ok) return _jordanFallbackMessage(data);
    const result = await res.json();
    const message = result.message || "";
    if (!message) return _jordanFallbackMessage(data);

    // Cache it
    try {
      localStorage.setItem("hb_jordan_card_cache", JSON.stringify({ key: cacheKey, message: message }));
    } catch(e) {}

    return message;
  } catch(e) {
    return _jordanFallbackMessage(data);
  }
}

async function fetchAndRenderScore() {
  const msgEl   = el("jordan-identity-message");
  const statsEl = el("jordan-identity-stats");
  if (!msgEl) return;

  // Demo mode
  if (localStorage.getItem("hb_demo_mode") === "true") {
    const demoData = {
      cir_count: 24, schedule_active: true, platforms_connected: 3,
      identity_complete: true, published_last_30: true, agent_name: "Brooke"
    };
    msgEl.textContent = _jordanFallbackMessage(demoData);
    const msg = await _jordanGenerateMessage(demoData);
    renderJordanIdentityCard(demoData, msg);
    return;
  }

  try {
    const res = await authFetch(BACKEND_URL + "/identity/score", { method:"POST", body:JSON.stringify({}) });
    if (!res.ok) return;
    const score = await res.json();
    if (!score || !score.pillars) return;

    const presence    = score.pillars.presence    || {};
    const foundation  = score.pillars.foundation  || {};
    const consistency = score.pillars.consistency || {};

    const cirCount         = score.cir_count != null ? score.cir_count : (presence.breakdown && presence.breakdown.total_approved != null ? presence.breakdown.total_approved : 0);
    const publishedLast30  = (presence.breakdown && presence.breakdown.published_last_30) ? true : false;
    const hasSchedule      = (consistency.breakdown && consistency.breakdown.has_schedule) ? true : false;
    const identityComplete = (foundation.score || 0) >= 20;
    const setup            = getSaved();
    const agentFirstName   = (setup.agentName || "").split(" ")[0] || "there";

    const _togglePlats = getActivePlatforms();
    const _oauthConns  = JSON.parse(localStorage.getItem("hb_oauth_connections") || "{}");
    const _oauthIds    = new Set(_togglePlats.map(function(p) { return p.id; }));
    const _oauthActive = Object.entries(_oauthConns).filter(function(e) { return e[1].connected && !_oauthIds.has(e[1].id || ""); });
    const platformsConn = _togglePlats.length + _oauthActive.length;

    const data = {
      cir_count:           cirCount,
      schedule_active:     hasSchedule,
      platforms_connected: platformsConn,
      identity_complete:   identityComplete,
      published_last_30:   publishedLast30,
      agent_name:          agentFirstName
    };

    // Show fallback immediately so Jordan is never blank
    msgEl.textContent = _jordanFallbackMessage(data);

    // Generate or load from cache
    const message = await _jordanGenerateMessage(data);
    renderJordanIdentityCard(data, message);
  } catch(e) {}
}

function renderJordanIdentityCard(data, message) {
  const msgEl   = el("jordan-identity-message");
  const statsEl = el("jordan-identity-stats");
  if (!msgEl) return;

  const cir_count         = data.cir_count         || 0;
  const schedule_active   = data.schedule_active   || false;
  const platforms_connected = data.platforms_connected || 0;

  msgEl.textContent = message || _jordanFallbackMessage(data);

  if (!statsEl) return;
  var chips = [];

  chips.push('<div class="jordan-stat-chip ' + (cir_count > 0 ? "stat-ok" : "") + '">' +
    '<span>Posts on record</span><span class="stat-value">' + cir_count + '</span></div>');

  chips.push('<div class="jordan-stat-chip ' + (schedule_active ? "stat-ok" : "stat-warn") + '">' +
    '<span>Schedule</span><span class="stat-value">' + (schedule_active ? "Active" : "Not set") + '</span></div>');

  chips.push('<div class="jordan-stat-chip ' + (platforms_connected > 0 ? "stat-ok" : "stat-warn") + '">' +
    '<span>Platforms</span><span class="stat-value">' + (platforms_connected > 0 ? platforms_connected + " connected" : "None connected") + '</span></div>');

  statsEl.innerHTML = chips.join("");
}

function renderScoreWidget(score) {
  // Legacy stub — score widget replaced by Jordan Identity Card.
}


// ─────────────────────────────────────────────
// SECTION 17: SETUP PANEL
// ─────────────────────────────────────────────
function renderDeliveryChips() {
  const icons = { instagram:"📸", tiktok:"🎵", youtube:"▶️", facebook:"👥", linkedin:"💼", twitter:"𝕏", google:"🔍", nextdoor:"🏘️", reddit:"🤖", email:"✉️", pinterest:"📌" };
  // Combine toggle-based platforms AND OAuth-connected platforms
  const togglePlatforms = getActivePlatforms();
  const oauthConns = JSON.parse(localStorage.getItem("hb_oauth_connections") || "{}");
  const oauthPlatforms = Object.entries(oauthConns)
    .filter(([, v]) => v.connected)
    .map(([id]) => ({ id, name: id.charAt(0).toUpperCase() + id.slice(1) }));
  // Merge, deduplicate by id
  const allIds = new Set(togglePlatforms.map(p => p.id));
  const combined = [...togglePlatforms];
  oauthPlatforms.forEach(p => { if (!allIds.has(p.id)) combined.push(p); });

  const noEl   = el("delivery-no-platforms");
  const chipsEl = el("delivery-platform-chips");
  if (!noEl || !chipsEl) return;
  if (!combined.length) {
    noEl.style.display   = "block";
    chipsEl.style.display = "none";
    return;
  }
  noEl.style.display   = "none";
  chipsEl.style.display = "flex";
  chipsEl.innerHTML = combined.map(p => {
    const icon = icons[p.id] || "📱";
    return `<div class="chip selected" style="display:flex;align-items:center;gap:5px;">${icon} ${p.name}</div>`;
  }).join("");
}


// ─────────────────────────────────────────────
// WEEKLY PROMPT CARD — shown at top of My Focus
// Fetches /weekly-prompt and renders a card with
// streak counter + this week's suggested situation
// + one-click "Write This Post" shortcut.
// ─────────────────────────────────────────────

// ─────────────────────────────────────────────
// AUTHORITY URL — shows agent their SEO page URL
// Displayed in setup panel so they know it exists
// and can share it / point their site at the RSS
// ─────────────────────────────────────────────
async function loadAuthorityUrl() {
  var card = el('authority-url-card');
  if (!card) return;

  // HB Marketing context shows platform-level info, not the personal agent slug
  if (getContentContext() === "hb_marketing") {
    card.innerHTML =
      '<div style="margin-bottom:6px">' +
        '<span style="font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-4)">Agent Authority Pages</span>' +
      '</div>' +
      '<div style="font-size:13px;color:var(--ink-2);">Each agent on AutoMates gets a public authority page at <span style="color:var(--gold);font-weight:600;">[slug].homebridgegroup.co</span> — Google-indexed, AI-searchable, and publicly verifiable via CIR™.</div>';
    return;
  }

  try {
    var res  = await authFetch(BACKEND_URL + '/setup/my-slug');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var data = await res.json();

    var url  = data.url  || '';
    var rss  = data.rss  || '';
    var isSet = data.set || false;

    if (!url) {
      card.innerHTML = '<div style="font-size:13px;color:var(--ink-4);">Save your Identity to generate your authority page URL.</div>';
      return;
    }

    card.innerHTML =
      '<div style="margin-bottom:10px">' +
        '<span style="font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-4)">Your Authority Page</span>' +
      '</div>' +
      '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">' +
        '<a href="' + url + '" target="_blank" style="font-size:15px;font-weight:600;color:var(--gold);word-break:break-all;">' + url + '</a>' +
        '<span style="font-size:11px;color:var(--ink-4)">· Google-indexed · AI-searchable · Publicly verifiable</span>' +
      '</div>' +
      (rss ? '<div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
        '<a href="' + rss + '" target="_blank" style="display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;color:var(--ink-3);background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:5px 12px;">📡 RSS Feed</a>' +
        '<span style="font-size:12px;color:var(--ink-4)">Paste this RSS URL into WordPress, Squarespace, or any CMS to auto-display your posts.</span>' +
      '</div>' : '') +
      (!isSet ? '<div style="margin-top:12px;font-size:12px;color:var(--ink-4);">Save your setup to lock in this URL permanently.</div>' : '');
  } catch(e) {
    card.innerHTML = '<div style="font-size:13px;color:var(--ink-4);">Save your Identity to generate your authority page URL.</div>';
  }
}

function customizeSlug() {
  var current = '';
  var custom = prompt('Customize your URL slug (letters, numbers, hyphens only):\n\nExample: kevin-lundy-denver\n\nThis becomes: kevin-lundy-denver.homebridgegroup.co', current);
  if (!custom) return;
  authFetch(BACKEND_URL + '/setup/slug', {
    method: 'POST',
    body: JSON.stringify({ slug: custom.toLowerCase().replace(/[^a-z0-9-]/g, '-') })
  }).then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.ok) {
        showToast('URL set: ' + d.url, 'success');
        loadAuthorityUrl();
      }
    }).catch(function() { showToast('Could not update URL.'); });
}

async function loadWeeklyPrompt() {
  const card = el("weekly-prompt-card");
  if (!card) return;

  card.innerHTML = `<div style="color:var(--ink-4);font-size:13px;padding:16px 0;">Loading this week’s prompt…</div>`;

  try {
    const res  = await authFetch(`${BACKEND_URL}/weekly-prompt`);
    const data = await res.json();

    const streakNum   = data.week_streak || 0;
    const situation   = data.situation   || "";
    const nudge       = data.nudge       || "";
    const isLighter   = data.situation_type === "lighter";

    // Streak flame — builds color intensity with streak
    const flameColor = streakNum === 0 ? "var(--ink-4)"
                     : streakNum < 4  ? "var(--gold)"
                     : streakNum < 12 ? "#E8621A"
                     : "#D42B0F";

    const streakLabel = streakNum === 0
      ? "Start your streak this week"
      : streakNum === 1
      ? "1 week published"
      : `${streakNum} weeks in a row`;

    // Clean display of situation (strip "Lighter Side: " prefix for display)
    const displaySituation = situation.replace(/^Lighter Side:/i, "").trim();
    const situationTag = isLighter
      ? `<span style="display:inline-flex;align-items:center;gap:5px;background:#FBF5E8;border:1px solid rgba(176,124,24,.2);border-radius:999px;padding:3px 10px;font-size:10px;font-weight:700;color:var(--gold);letter-spacing:.08em;text-transform:uppercase;">😄 Lighter Side</span>`
      : `<span style="display:inline-flex;align-items:center;gap:5px;background:var(--blue-soft,#EEF2FB);border:1px solid rgba(20,70,184,.15);border-radius:999px;padding:3px 10px;font-size:10px;font-weight:700;color:var(--blue);letter-spacing:.08em;text-transform:uppercase;">✦ This Week</span>`;

    card.innerHTML = `
      <div style="display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:start;">

        <!-- Streak column -->
        <div style="text-align:center;min-width:72px;">
          <div style="font-size:42px;line-height:1;margin-bottom:4px;">🔥</div>
          <div style="font-family:Cormorant Garant,serif;font-size:32px;font-weight:600;line-height:1;color:${flameColor};margin-bottom:4px;">${streakNum}</div>
          <div style="font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-4);">${streakNum === 1 ? "week" : "weeks"}</div>
        </div>

        <!-- Prompt column -->
        <div>
          <div style="margin-bottom:12px;">${situationTag}</div>
          <div style="font-family:Cormorant Garant,serif;font-size:20px;font-weight:500;color:var(--ink);line-height:1.3;margin-bottom:10px;">${displaySituation}</div>
          <div style="font-size:13px;color:var(--ink-3);margin-bottom:18px;font-style:italic;">${nudge}</div>
          <button data-situation="${situation.replace(/"/g,'&quot;')}" onclick="useWeeklyPrompt(this.dataset.situation)" style="background:var(--blue);color:#fff;border:none;border-radius:999px;padding:10px 22px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:opacity .2s;" onmouseover="this.style.opacity='.82'" onmouseout="this.style.opacity='1'">
            Write this post →
          </button>
        </div>

      </div>
    `;
  } catch(e) {
    card.innerHTML = '<div style="font-size:13px;color:var(--ink-4);padding:8px 0;">Could not load weekly prompt.</div>';
  }
}

function useWeeklyPrompt(situation) {
  // Pre-fill the situation in content engine and navigate there
  navigateTo("content-engine-panel");
  // Small delay to let panel render
  setTimeout(() => {
    const dropdown = el("situation-select");
    if (dropdown) {
      // Add as first option if not already present
      let found = false;
      for (let i = 0; i < dropdown.options.length; i++) {
        if (dropdown.options[i].value === situation) {
          dropdown.selectedIndex = i;
          found = true;
          break;
        }
      }
      if (!found) {
        const opt = document.createElement("option");
        opt.value = situation;
        opt.textContent = situation.replace(/^Lighter Side:/i, "").trim();
        dropdown.insertBefore(opt, dropdown.options[1]);
        dropdown.selectedIndex = 1;
      }
    }
    showToast("Situation loaded — generate when ready.", "info");
  }, 300);
}

function loadSetup() {
  const ctx = getViewContext();
  // Office context — render broker office setup fields
  if (ctx === "office" || ctx === "broker") { _loadOfficeSetup(); return; }
  // Team context — render team setup fields
  if (ctx === "team") { _loadTeamSetup(); return; }
  // Platform, partner, admin — Setup not available
  if (ctx === "super_admin" || ctx === "admin" || ctx === "support" || ctx === "partner") {
    const panel = el("setup-panel");
    if (panel) panel.innerHTML = `
      <div style="max-width:560px;margin:80px auto;text-align:center;padding:0 24px;">
        <div style="font-size:32px;margin-bottom:16px;">⚙︎</div>
        <div style="font-size:18px;font-weight:700;color:var(--ink);margin-bottom:8px;">Focus isn't available here</div>
        <div style="font-size:14px;color:var(--ink-3);line-height:1.7;margin-bottom:24px;">
          Focus configures your content niches and schedule and is only available in your
          <strong>My Work</strong> workspace. Switch to My Work to manage your niches and content schedule.
        </div>
        <button class="btn-primary" style="padding:11px 28px;font-size:14px;border-radius:10px;"
          onclick="
            const u=JSON.parse(localStorage.getItem('hb_user')||'null');
            if(u){setViewContext('agent');bootForRole(u,true);}
          ">Go to My Work →</button>
      </div>`;
    return;
  }
  const saved = getSaved();
  selectedPrimaryNiches = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  selectedSubNiches     = Array.isArray(saved.subNiches)     ? saved.subNiches     : [];
  // If no sub-niches saved yet, auto-select all sub-niches for existing primary niches
  if (!selectedSubNiches.length && selectedPrimaryNiches.length) {
    selectedSubNiches = selectedPrimaryNiches.flatMap(n => (NICHE_DATA[n]||[]).slice(0,3));
  }
  // Pre-open categories that have selected niches
  _nicheAccordionOpen = {};
  Object.entries(NICHE_CATEGORIES).forEach(([cat, niches]) => {
    if (niches.some(n => selectedPrimaryNiches.includes(n))) {
      _nicheAccordionOpen[cat] = true;
    }
  });
  // Load audience description
  const audEl = el("audience-description");
  if (audEl && saved.audienceDescription) audEl.value = saved.audienceDescription;
  renderNicheAccordion(); renderCustomNicheChips();
  // Load authority URL and identity score — both live on Identity panel
  loadAuthorityUrl();
  fetchAndRenderScore();
  // Load voice setup status — Session 51
  _voiceLoadStatus();
}

// Focus Save — saves niche and schedule configuration only
// Profile fields (voice, platforms, disclaimer etc) autosave separately
el("save-setup-btn")?.addEventListener("click", async () => {
  const saved = getSaved();
  const data = {
    ...saved,
    audienceDescription: el("audience-description")?.value.trim() || saved.audienceDescription || "",
    primaryNiches:  selectedPrimaryNiches,
    subNiches:      selectedSubNiches,
  };
  const btn = el("save-setup-btn"); const msg = el("save-success");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
  try {
    const res = await (_isMarketingContext()
      ? authFetch(`${BACKEND_URL}/marketing-setup/save`, { method:"POST", body:JSON.stringify({ setup:data }) })
      : authFetch(`${BACKEND_URL}/setup/save`,           { method:"POST", body:JSON.stringify({ setup:data }) }));
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = err.detail?.message || err.detail || "Could not save — please try again.";
      showToast(detail);
      if (btn) { btn.disabled = false; btn.textContent = "Save & Go →"; }
      return;
    }
  } catch(e) {
    showToast("Connection error — please try again.");
    if (btn) { btn.disabled = false; btn.textContent = "Save & Go →"; }
    return;
  }
  localStorage.setItem(getSetupKey(), JSON.stringify(data));
  gsMarkDone(2);
  if (btn) { btn.disabled = false; btn.textContent = "Saved ✓"; btn.style.background = "var(--blue)"; }
  renderScheduleUI();
  const hasContent = Array.isArray(_cachedLibrary) && _cachedLibrary.length > 0;
  if (hasContent) {
    if (msg) { msg.textContent = "Focus saved."; msg.style.display = "block"; }
    setTimeout(() => {
      if (btn) { btn.textContent = "Save & Go →"; btn.style.background = ""; }
      if (msg) msg.style.display = "none";
    }, 2000);
  } else {
    if (msg) { msg.textContent = "Focus saved — taking you to the Content Engine."; msg.style.display = "block"; }
    setTimeout(() => {
      if (btn) { btn.textContent = "Save & Go →"; btn.style.background = ""; }
      if (msg) msg.style.display = "none";
      navigateTo("content-engine-panel");
    }, 1400);
  }
});

// ─────────────────────────────────────────────
// SECTION 18: PROFILE PANEL
// ─────────────────────────────────────────────
// ── Profile mode flag: "guided" (from GS) or "full" (from nav) ──
let _profileMode = "guided";
function enterFullProfile() {
  _profileMode = "full";
  renderProfilePanel();
}

function toggleAccordion(id) {
  const body    = el("acc-body-" + id);
  const chevron = el("acc-chevron-" + id);
  if (!body) return;
  const isOpen = body.style.display !== "none";
  body.style.display    = isOpen ? "none" : "block";
  if (chevron) chevron.classList.toggle("open", !isOpen);
  // Load billing when that section opens
  if (id === "billing" && !isOpen) loadBillingStatus();
}

function updateProfileCompleteness() {
  const saved = getSaved();
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");
  const checks = [
    !!(user?.agent_name || saved.agentName),
    !!(user?.brokerage  || saved.brokerage),
    !!(saved.market),
    !!(saved.disclaimer || getDisclaimer()),
    !!(Array.isArray(saved.platforms) && saved.platforms.length),
    !!(saved.shortBio || saved.brandVoice),
  ];
  const pct  = Math.round(checks.filter(Boolean).length / checks.length * 100);
  const fill = el("profile-completeness-fill");
  const pctEl= el("profile-completeness-pct");
  const lbl  = el("profile-completeness-label");
  if (fill) fill.style.width = pct + "%";
  if (pctEl) pctEl.textContent = pct + "%";
  if (lbl)  lbl.textContent = pct >= 80 ? "Profile looking great." : pct >= 50 ? "Good start — a few more details help." : "Tell us about yourself.";
  // Accordion status dots
  const dotAccount   = el("acc-dot-account");
  const dotIdentity  = el("acc-dot-identity");
  const dotPlatforms = el("acc-dot-platforms");
  const dotDisclaim  = el("acc-dot-disclaimer");
  if (dotAccount)   { const on = !!(user?.agent_name); dotAccount.textContent   = on?"●":"○"; dotAccount.classList.toggle("done",on); }
  if (dotIdentity)  { const on = !!(saved.market||saved.shortBio); dotIdentity.textContent  = on?"●":"○"; dotIdentity.classList.toggle("done",on); }
  if (dotPlatforms) { const on = !!(Array.isArray(saved.platforms)&&saved.platforms.length); dotPlatforms.textContent = on?"●":"○"; dotPlatforms.classList.toggle("done",on); }
  if (dotDisclaim)  { const on = !!(saved.disclaimer||getDisclaimer()); dotDisclaim.textContent  = on?"●":"○"; dotDisclaim.classList.toggle("done",on); }
  // Accordion summaries
  const sumAccount  = el("acc-summary-account");
  const sumIdent    = el("acc-summary-identity");
  const sumPlat     = el("acc-summary-platforms");
  const sumDisclaim = el("acc-summary-disclaimer");
  const sumLang     = el("acc-summary-language");
  if (sumAccount)  sumAccount.textContent  = user?.agent_name ? (user.agent_name + (user.brokerage ? " · " + user.brokerage : "")) : "Not set";
  // "How I Post" summary shows connected platforms + disclaimer status
  if (sumIdent) {
    const oauthConns2 = JSON.parse(localStorage.getItem("hb_oauth_connections") || "{}");
    const connectedNames = Object.entries(oauthConns2).filter(([,v])=>v.connected).map(([id])=>id.charAt(0).toUpperCase()+id.slice(1));
    const toggleActive = Array.isArray(saved.platforms) ? saved.platforms.map(p=>p.name) : [];
    const allPlatNames = [...new Set([...connectedNames, ...toggleActive])];
    const hasDisclaimer = !!(saved.disclaimer || getDisclaimer());
    if (allPlatNames.length) {
      sumIdent.textContent = allPlatNames.join(", ") + (hasDisclaimer ? " · Disclaimer set" : " · No disclaimer yet");
    } else {
      sumIdent.textContent = hasDisclaimer ? "Disclaimer set" : "No platforms or disclaimer yet";
    }
  }
  if (sumPlat)     sumPlat.textContent     = Array.isArray(saved.platforms) && saved.platforms.length ? saved.platforms.map(p=>p.name).join(", ") : "None selected";
  if (sumDisclaim) sumDisclaim.textContent = saved.disclaimer ? saved.disclaimer.slice(0,40)+"…" : "Not set";
  if (sumLang)     sumLang.textContent     = ({english:"English",spanish:"Spanish",bilingual:"Bilingual"})[getLanguagePref()] || "English";
}


// ── Marketing context profile adjustments ──
// Hides agent-specific fields, relabels Zone of Greatness for a platform company
function _applyMarketingProfileContext() {
  // Hide agent-only sections
  const hide = ["section-licensed-state","section-service-areas","section-designations","section-mls"];
  hide.forEach(id => {
    const el_ = document.getElementById(id);
    if (el_) el_.style.display = "none";
  });

  // Relabel Zone of Greatness section for a platform company
  const zog = document.getElementById("section-zone-of-greatness");
  if (zog) {
    // Section heading
    const heading = zog.querySelector("div[style*='font-size:13px'][style*='font-weight:700']");
    if (heading) heading.innerHTML = 'Our Brand Identity <span style="font-size:12px;font-weight:400;color:var(--blue);">Makes every post sound like HomeBridge, not a generic tech company</span>';

    // Sub-hint
    const hint = zog.querySelector("div[style*='font-size:12px'][style*='color:var(--text-muted)']");
    if (hint) hint.textContent = "These four questions shape every piece of content. Be honest about what HomeBridge is, why it exists, and who it serves.";

    // Field labels — find by textarea/input ID
    const labelMap = {
      "origin-story":         { label:"Why we built HomeBridge", hint:"the honest answer", placeholder:"e.g. Kevin's parents lost their home in 2008 because nobody explained the terms to them. That's why HomeBridge exists." },
      "unfair-advantage":     { label:"Our unfair advantage", hint:"what HomeBridge does that no generic AI tool can replicate", placeholder:"e.g. CIR™ credentialing + PaperTrail™ audit trail + hyper-local signal intelligence that no generic tool provides." },
      "signature-perspective":{ label:"Our signature belief", hint:"something about real estate marketing most platforms get wrong", placeholder:"e.g. Generic AI gave every agent a voice. Which means sounding expert no longer wins. Proof does." },
      "not-for-client":       { label:"Who HomeBridge is NOT for", hint:"being specific attracts the right brokers and agents", placeholder:"e.g. Agents who want a content calendar. We build market authority, not a posting schedule." },
    };
    Object.entries(labelMap).forEach(([fieldId, cfg]) => {
      const field = document.getElementById(fieldId);
      if (!field) return;
      const wrapper = field.closest(".profile-field");
      if (!wrapper) return;
      const lbl = wrapper.querySelector("label");
      if (lbl) lbl.innerHTML = cfg.label + ` <span style="font-weight:400;font-size:11px;color:var(--text-muted);text-transform:none;letter-spacing:0;">${cfg.hint}</span>`;
      field.placeholder = cfg.placeholder;
    });
  }

  // Update Content Identity section hint
  const ciHint = document.querySelector(".profile-section-hint");
  if (ciHint && ciHint.textContent.includes("your market, voice, credentials")) {
    ciHint.textContent = "This shapes every piece of content HomeBridge generates about itself — our voice, audience, and positioning. Set it once and it's woven into everything.";
  }

  // Update Short Bio placeholder
  const bio = document.getElementById("short-bio");
  if (bio) bio.placeholder = "e.g. HomeBridge is the only AI content platform built specifically for real estate professionals — combining hyper-local market intelligence, authentic voice generation, and real compliance infrastructure.";

  // Update Brand Voice placeholder
  const bv = document.getElementById("brand-voice");
  if (bv) bv.placeholder = "e.g. Authoritative but accessible. Forward-thinking. Never corporate. Always direct. Speaks to the future of real estate without dismissing the present.";

  // Update market placeholder
  const mkt = document.getElementById("market");
  if (mkt) { mkt.placeholder = "e.g. Real Estate Technology"; }

  // Update Business Name placeholder
  const bn = document.getElementById("business-name");
  if (bn) { bn.placeholder = "HomeBridge Group"; }
}

function renderAdminAccountPanel() {
  // Admin/super_admin context — show account management only, no content identity fields
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const profilePanel = el("profile-panel");
  if (!profilePanel) return;

  // Build a minimal account-only view inside the profile panel
  const existing     = el("admin-account-view");
  const agentContent = el("profile-agent-content");
  if (existing) {
    // Already rendered — just refresh field values and ensure agent content is hidden
    if (agentContent) agentContent.style.display = "none";
    if (el("profile-name"))               el("profile-name").value               = user.agent_name || "";
    if (el("profile-email"))              el("profile-email").value              = user.email      || "";
    if (el("profile-phone"))              el("profile-phone").value              = user.phone      || "";
    if (el("profile-notification-email")) el("profile-notification-email").value = user.notification_email || "";
    return;
  }

  // Hide the full profile UI, show only account section
  const guided = el("profile-guided");
  const full   = el("profile-full");
  if (guided)       guided.style.display       = "none";
  if (full)         full.style.display         = "none";
  if (agentContent) agentContent.style.display = "none";

  const wrap = document.createElement("div");
  wrap.id = "admin-account-view";
  wrap.style.cssText = "padding:32px;max-width:560px;";
  wrap.innerHTML = `
    <div style="font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);margin-bottom:24px;">Account Settings</div>
    <div style="display:flex;flex-direction:column;gap:18px;">
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Name</label>
        <input id="profile-name" type="text" value="${user.agent_name||''}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Email</label>
        <input id="profile-email" type="email" value="${user.email||''}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Phone</label>
        <input id="profile-phone" type="tel" value="${user.phone||''}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Notification Email</label>
        <input id="profile-notification-email" type="email" value="${user.notification_email||''}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <div style="font-size:11px;color:var(--ink-3);margin-top:5px;">Where approval and system notifications are sent.</div>
      </div>
      <div id="admin-account-msg" style="display:none;font-size:13px;color:var(--green);font-weight:600;"></div>
      <button onclick="saveAdminAccount()" style="width:100%;padding:12px;background:var(--blue);color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Save Account Info</button>
      <div style="padding-top:16px;border-top:1px solid var(--border);">
        <div style="font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:10px;">Change Password</div>
        <div style="display:flex;flex-direction:column;gap:10px;">
          <input id="admin-pw-current" type="password" placeholder="Current password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
          <input id="admin-pw-new" type="password" placeholder="New password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
          <button onclick="saveAdminPassword()" style="padding:11px;background:var(--surface);color:var(--ink);border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Update Password</button>
          <div id="admin-pw-msg" style="display:none;font-size:13px;font-weight:600;"></div>
        </div>
      </div>
    </div>
  `;
  profilePanel.appendChild(wrap);
}

// ─────────────────────────────────────────────
// ORG PROFILE — Office and Team Profile & Identity
// ─────────────────────────────────────────────

async function loadOrgProfile(type) {
  const panel = el("profile-panel");
  if (!panel) return;

  // Remove any previous context views
  el("context-account-view")?.remove();
  el("admin-account-view")?.remove();
  el("org-profile-view")?.remove();

  // Show loading state
  const loading = document.createElement("div");
  loading.id = "org-profile-view";
  loading.style.cssText = "padding:32px;max-width:680px;";
  loading.innerHTML = `<div style="font-size:13px;color:var(--ink-3);">Loading profile…</div>`;
  panel.appendChild(loading);

  // Fetch current profile from server using existing endpoints
  let profile = {};
  try {
    const endpoint = type === "office" ? "/office/setup/get" : "/team/setup/get";
    const res  = await authFetch(`${BACKEND_URL}${endpoint}`);
    const data = await res.json();
    profile = data.setup || {};
  } catch(e) { /* use empty profile */ }

  const user = JSON.parse(localStorage.getItem("hb_user") || "null") || {};
  const isOffice = type === "office";
  const titleLabel = isOffice ? "My Office" : "My Team";

  el("org-profile-view").innerHTML = `
    <div style="font-size:20px;font-weight:800;color:var(--ink);letter-spacing:-.02em;margin-bottom:4px;">${titleLabel} Profile</div>
    <div style="font-size:13px;color:var(--ink-3);margin-bottom:28px;line-height:1.55;">
      ${isOffice
        ? "Your office identity — used in compliance records and agent content disclosures."
        : "Your team identity — used in compliance records and agent content disclosures."}
    </div>

    <!-- Identity fields -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;">
      <div>
        <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">
          ${isOffice ? "Office Name" : "Team Name"} <span style="color:var(--red);">*</span>
        </label>
        <input id="org-name" type="text" value="${_escHtml(profile.name||'')}"
          placeholder="${isOffice ? 'e.g. Lundy Real Estate Group' : 'e.g. The Lundy Team'}"
          style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">
          Brokerage Name <span style="color:var(--red);">*</span>
        </label>
        <input id="org-brokerage" type="text" value="${_escHtml(profile.brokerage||'')}"
          placeholder="e.g. eXp Realty"
          style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      ${isOffice ? `
      <div>
        <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">Broker of Record</label>
        <input id="org-broker-of-record" type="text" value="${_escHtml(profile.brokerOfRecord||'')}"
          placeholder="Full legal name"
          style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>` : `
      <div>
        <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">Team Lead Name</label>
        <input id="org-team-lead" type="text" value="${_escHtml(profile.teamLead||user.agent_name||'')}"
          placeholder="Full name"
          style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>`}
      <div>
        <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">Phone</label>
        <input id="org-phone" type="tel" value="${_escHtml(profile.phone||'')}"
          placeholder="(303) 555-0100"
          style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
    </div>

    <div style="margin-bottom:20px;">
      <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">
        ${isOffice ? "Office" : "Team"} Address
      </label>
      <input id="org-address" type="text" value="${_escHtml(profile.address||'')}"
        placeholder="123 Main St, Denver, CO 80202"
        style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
    </div>

    ${!isOffice ? `
    <div style="margin-bottom:20px;">
      <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">Team Website <span style="font-weight:400;text-transform:none;letter-spacing:0;font-size:11px;color:var(--ink-4);">optional</span></label>
      <input id="org-website" type="url" value="${_escHtml(profile.website||'')}"
        placeholder="https://yourteam.com"
        style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
    </div>` : ""}

    <!-- Disclaimer section -->
    <div style="padding:20px;background:var(--bg-sunken,#f8f8f6);border-radius:12px;margin-bottom:28px;">
      <div style="font-size:13px;font-weight:700;color:var(--ink);margin-bottom:4px;">${isOffice ? "Office" : "Team"} Disclaimer</div>
      <div style="font-size:12px;color:var(--ink-3);margin-bottom:14px;line-height:1.6;">
        Control how your office disclaimer appears — or doesn't — on agent content.
      </div>
      <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:14px;">
        <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;">
          <input type="radio" name="org-disclaimer-mode" value="none"
            ${(profile.disclaimerMode||'none')==='none'?'checked':''} style="margin-top:3px;cursor:pointer;" />
          <div>
            <div style="font-size:13px;font-weight:600;color:var(--ink);">No office disclaimer</div>
            <div style="font-size:11px;color:var(--ink-4);line-height:1.5;">Each agent manages their own disclaimer entirely.</div>
          </div>
        </label>
        <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;">
          <input type="radio" name="org-disclaimer-mode" value="papertrail"
            ${(profile.disclaimerMode||'')==='papertrail'?'checked':''} style="margin-top:3px;cursor:pointer;" />
          <div>
            <div style="font-size:13px;font-weight:600;color:var(--ink);">PaperTrail™ only</div>
            <div style="font-size:11px;color:var(--ink-4);line-height:1.5;">Office disclaimer appears in the compliance PDF record only — not on public posts. Keeps posts clean.</div>
          </div>
        </label>
        <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;">
          <input type="radio" name="org-disclaimer-mode" value="override"
            ${(profile.disclaimerMode||'')==='override'?'checked':''} style="margin-top:3px;cursor:pointer;" />
          <div>
            <div style="font-size:13px;font-weight:600;color:var(--ink);">Replace agent disclaimer</div>
            <div style="font-size:11px;color:var(--ink-4);line-height:1.5;">Office disclaimer replaces the individual agent disclaimer on all posts. Full control over public-facing language.</div>
          </div>
        </label>
      </div>
      <div id="org-disclaimer-text-wrap" style="display:${(profile.disclaimerMode&&profile.disclaimerMode!=='none')?'block':'none'};">
        <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">
          Disclaimer Text <span style="font-weight:400;text-transform:none;letter-spacing:0;font-size:11px;color:var(--ink-4);">optional — leave blank to use agent's own</span>
        </label>
        <textarea id="org-disclaimer-text" rows="3"
          placeholder="e.g. Licensed in Colorado. All content is for informational purposes only. eXp Realty."
          style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:13px;outline:none;resize:vertical;">${_escHtml(profile.disclaimerText||'')}</textarea>
      </div>
    </div>

    <!-- Account Settings -->
    <div style="padding-top:20px;border-top:1px solid var(--border);margin-bottom:20px;">
      <div style="font-size:13px;font-weight:700;color:var(--ink);margin-bottom:16px;">Account Settings</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">
        <div>
          <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">Your Name</label>
          <input id="org-acct-name" type="text" value="${_escHtml(user.agent_name||'')}"
            style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        </div>
        <div>
          <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">Email</label>
          <input id="org-acct-email" type="email" value="${_escHtml(user.email||'')}"
            style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        </div>
        <div style="grid-column:1/-1;">
          <label style="display:block;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin-bottom:6px;">Notification Email <span style="font-weight:400;text-transform:none;letter-spacing:0;">optional</span></label>
          <input id="org-acct-notif" type="email" value="${_escHtml(user.notification_email||'')}"
            placeholder="Where approval alerts and system notifications go"
            style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        </div>
      </div>
    </div>

    <!-- Password -->
    <div style="padding-top:16px;border-top:1px solid var(--border);margin-bottom:28px;">
      <div style="font-size:13px;font-weight:700;color:var(--ink);margin-bottom:12px;">Change Password</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <input id="org-pw-current" type="password" placeholder="Current password"
          style="padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <input id="org-pw-new" type="password" placeholder="New password"
          style="padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div id="org-pw-msg" style="display:none;font-size:13px;font-weight:600;margin-top:8px;"></div>
    </div>

    <!-- Save buttons -->
    <div id="org-profile-msg" style="display:none;font-size:13px;font-weight:600;margin-bottom:12px;"></div>
    <div style="display:flex;gap:12px;">
      <button onclick="saveOrgProfile('${type}')"
        style="flex:1;padding:13px;background:var(--blue);color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">
        Save ${titleLabel} Profile
      </button>
      <button onclick="saveOrgPassword()"
        style="padding:13px 20px;background:var(--surface,#fff);color:var(--ink);border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">
        Update Password
      </button>
    </div>
  `;

  // Wire disclaimer mode radio buttons to show/hide text field
  document.querySelectorAll('input[name="org-disclaimer-mode"]').forEach(radio => {
    radio.addEventListener("change", () => {
      const wrap = el("org-disclaimer-text-wrap");
      if (wrap) wrap.style.display = radio.value !== "none" ? "block" : "none";
    });
  });
}

async function saveOrgProfile(type) {
  const msg = el("org-profile-msg");

  // Gather profile fields
  const profile = {
    name:           el("org-name")?.value.trim()            || "",
    brokerage:      el("org-brokerage")?.value.trim()       || "",
    phone:          el("org-phone")?.value.trim()           || "",
    address:        el("org-address")?.value.trim()         || "",
    disclaimerMode: document.querySelector('input[name="org-disclaimer-mode"]:checked')?.value || "none",
    disclaimerText: el("org-disclaimer-text")?.value.trim() || "",
  };
  if (type === "office") {
    profile.brokerOfRecord = el("org-broker-of-record")?.value.trim() || "";
  } else {
    profile.teamLead = el("org-team-lead")?.value.trim() || "";
    profile.website  = el("org-website")?.value.trim()   || "";
  }

  // Validate required fields
  if (!profile.name) { showToast(`Please enter a ${type === "office" ? "office" : "team"} name.`); return; }
  if (!profile.brokerage) { showToast("Please enter a brokerage name."); return; }

  try {
    // Save org profile to server using existing endpoints
    const endpoint = type === "office" ? "/office/setup/save" : "/team/setup/save";
    const r = await authFetch(`${BACKEND_URL}${endpoint}`, {
      method: "POST",
      body:   JSON.stringify({ setup: profile }),
    });
    if (!r.ok) throw new Error();

    // Save account info (name, email, notification email)
    const user   = JSON.parse(localStorage.getItem("hb_user") || "null") || {};
    const name   = el("org-acct-name")?.value.trim()  || "";
    const email  = el("org-acct-email")?.value.trim() || "";
    const notif  = el("org-acct-notif")?.value.trim() || "";
    const r2 = await authFetch(`${BACKEND_URL}/auth/profile`, {
      method: "POST", body: JSON.stringify({ agent_name: name, email }),
    });
    if (notif) {
      await authFetch(`${BACKEND_URL}/auth/profile/notification-email`, {
        method: "POST", body: JSON.stringify({ notification_email: notif }),
      });
    }
    if (r2.ok) {
      user.agent_name = name; user.email = email;
      if (notif) user.notification_email = notif;
      localStorage.setItem("hb_user", JSON.stringify(user));
      updateAvatar();
    }

    if (msg) { msg.textContent = "✓ Profile saved."; msg.style.color = "var(--green)"; msg.style.display = "block"; setTimeout(() => { if(msg) msg.style.display = "none"; }, 2500); }
  } catch(e) {
    if (msg) { msg.textContent = "Save failed — please try again."; msg.style.color = "var(--red)"; msg.style.display = "block"; }
  }
}

async function saveOrgPassword() {
  const current = el("org-pw-current")?.value || "";
  const next    = el("org-pw-new")?.value     || "";
  const msg     = el("org-pw-msg");
  if (!current || !next) { if(msg){msg.textContent="Enter both current and new password.";msg.style.display="block";msg.style.color="var(--red)";} return; }
  try {
    const r = await authFetch(`${BACKEND_URL}/auth/change-password`, {
      method:"POST", body:JSON.stringify({ current_password:current, new_password:next })
    });
    if (r.ok) {
      if(el("org-pw-current")) el("org-pw-current").value = "";
      if(el("org-pw-new"))     el("org-pw-new").value     = "";
      if(msg){msg.textContent="✓ Password updated";msg.style.display="block";msg.style.color="var(--green)";setTimeout(()=>{if(msg)msg.style.display="none";},2500);}
    } else {
      const d = await r.json().catch(()=>({}));
      if(msg){msg.textContent=d.detail||"Incorrect current password.";msg.style.display="block";msg.style.color="var(--red)";}
    }
  } catch(e) {
    if(msg){msg.textContent="Error — try again.";msg.style.display="block";msg.style.color="var(--red)";}
  }
}

function renderHBMarketingProfile() {
  // HB Marketing profile — same structure as agent My Work profile
  // but using hb_hb_setup storage key and HomeBridge-specific niche taxonomy.
  // Renders the full profile-agent-content but pre-loaded with marketing setup.
  const agentContent = el("profile-agent-content");
  const panel = el("profile-panel");
  if (!panel) return;

  el("context-account-view")?.remove();
  el("admin-account-view")?.remove();
  el("org-profile-view")?.remove();

  // Show the full agent profile UI — it uses getSetupKey() which returns
  // hb_hb_setup when ctx === 'marketing', so data stays completely separate.
  if (agentContent) agentContent.style.display = "";

  // Switch panel title to reflect marketing context
  const panelTitle    = panel.querySelector(".panel-title");
  const panelSubtitle = panel.querySelector(".panel-subtitle");
  if (panelTitle)    panelTitle.textContent    = "HB Marketing Profile";
  if (panelSubtitle) panelSubtitle.textContent = "HomeBridge brand identity — used for company content targeting brokerages, title companies, and real estate professionals.";

  // Load the marketing setup into the profile fields
  const saved = getSaved(); // returns hb_hb_setup in marketing context
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null") || {};

  if (el("profile-name"))      el("profile-name").value      = user.agent_name || "";
  if (el("profile-email"))     el("profile-email").value     = user.email      || "";
  if (el("profile-brokerage")) el("profile-brokerage").value = saved.businessName || "The Home Bridge Group";
  if (el("market"))            el("market").value            = saved.market    || "";
  if (el("short-bio"))         el("short-bio").value         = saved.shortBio  || "";
  if (el("brand-voice"))       el("brand-voice").value       = saved.brandVoice || "";
  if (el("words-avoid"))       el("words-avoid").value       = saved.wordsAvoid || "";
  if (el("words-prefer"))      el("words-prefer").value      = saved.wordsPrefer || "";
  if (el("origin-story"))      el("origin-story").value      = saved.originStory || "";
  if (el("unfair-advantage"))  el("unfair-advantage").value  = saved.unfairAdvantage || "";
  if (el("signature-perspective")) el("signature-perspective").value = saved.signaturePerspective || "";
  if (el("not-for-client"))    el("not-for-client").value    = saved.notForClient || "";

  // Update Zone of Greatness labels for marketing context
  const originLabel = document.querySelector('label[for="origin-story"], textarea#origin-story')?.closest('.profile-field')?.querySelector('label');
  if (originLabel) originLabel.childNodes[0].textContent = "Why HomeBridge was built ";

  renderCtaMethods();
  setTimeout(clearAutofill, 300);
}

function renderContextAccountPanel(contextLabel, contextHint) {
  // Shared account-only panel for non-agent contexts (office, team, marketing, partner).
  // Shows name/email/password — no agent content identity fields.
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const profilePanel = el("profile-panel");
  if (!profilePanel) return;

  // Remove any previous context panel
  el("context-account-view")?.remove();
  el("admin-account-view")?.remove();

  const wrap = document.createElement("div");
  wrap.id = "context-account-view";
  wrap.style.cssText = "padding:32px;max-width:560px;";
  wrap.innerHTML = `
    <div style="font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);margin-bottom:6px;">Account Settings</div>
    <div style="font-size:12px;color:var(--ink-4);margin-bottom:24px;line-height:1.55;">${contextHint}</div>
    <div style="display:flex;flex-direction:column;gap:18px;">
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Name</label>
        <input id="ctx-profile-name" type="text" value="${_escHtml(user.agent_name||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Email</label>
        <input id="ctx-profile-email" type="email" value="${_escHtml(user.email||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Notification Email</label>
        <input id="ctx-profile-notif" type="email" value="${_escHtml(user.notification_email||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <div style="font-size:11px;color:var(--ink-3);margin-top:5px;">Where approval and system notifications are sent.</div>
      </div>
      <div id="ctx-account-msg" style="display:none;font-size:13px;font-weight:600;"></div>
      <button onclick="saveContextAccount()" style="width:100%;padding:12px;background:var(--blue);color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Save Account Info</button>
      <div style="padding-top:16px;border-top:1px solid var(--border);">
        <div style="font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:10px;">Change Password</div>
        <div style="display:flex;flex-direction:column;gap:10px;">
          <input id="ctx-pw-current" type="password" placeholder="Current password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
          <input id="ctx-pw-new" type="password" placeholder="New password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
          <button onclick="saveContextPassword()" style="padding:11px;background:var(--surface);color:var(--ink);border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Update Password</button>
          <div id="ctx-pw-msg" style="display:none;font-size:13px;font-weight:600;"></div>
        </div>
      </div>
    </div>
  `;
  profilePanel.appendChild(wrap);
}

async function saveContextAccount() {
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const name  = el("ctx-profile-name")?.value.trim()  || "";
  const email = el("ctx-profile-email")?.value.trim() || "";
  const notif = el("ctx-profile-notif")?.value.trim() || "";
  const msg   = el("ctx-account-msg");
  try {
    const r = await authFetch(`${BACKEND_URL}/auth/profile`, {
      method:"POST", body:JSON.stringify({ agent_name:name, email })
    });
    if (notif) {
      await authFetch(`${BACKEND_URL}/auth/profile/notification-email`, {
        method:"POST", body:JSON.stringify({ notification_email:notif })
      });
    }
    if (r.ok) {
      user.agent_name = name; user.email = email;
      if (notif) user.notification_email = notif;
      localStorage.setItem("hb_user", JSON.stringify(user));
      updateAvatar();
      if (msg) { msg.textContent = "✓ Saved"; msg.style.display = "block"; msg.style.color = "var(--green)"; setTimeout(() => { if(msg) msg.style.display = "none"; }, 2500); }
    }
  } catch(e) {
    if (msg) { msg.textContent = "Save failed — try again."; msg.style.display = "block"; msg.style.color = "var(--red)"; }
  }
}

async function saveContextPassword() {
  const current = el("ctx-pw-current")?.value || "";
  const next    = el("ctx-pw-new")?.value     || "";
  const msg     = el("ctx-pw-msg");
  if (!current || !next) { if(msg){msg.textContent="Enter both current and new password.";msg.style.display="block";msg.style.color="var(--red)";} return; }
  try {
    const r = await authFetch(`${BACKEND_URL}/auth/change-password`, {
      method:"POST", body:JSON.stringify({ current_password:current, new_password:next })
    });
    if (r.ok) {
      if(el("ctx-pw-current")) el("ctx-pw-current").value = "";
      if(el("ctx-pw-new"))     el("ctx-pw-new").value     = "";
      if(msg){msg.textContent="✓ Password updated";msg.style.display="block";msg.style.color="var(--green)";setTimeout(()=>{if(msg)msg.style.display="none";},2500);}
    } else {
      const d = await r.json().catch(()=>({}));
      if(msg){msg.textContent=d.detail||"Incorrect current password.";msg.style.display="block";msg.style.color="var(--red)";}
    }
  } catch(e) {
    if(msg){msg.textContent="Error — try again.";msg.style.display="block";msg.style.color="var(--red)";}
  }
}

// ─── OFFICE PROFILE ───────────────────────────────────────────────────────────

async function renderOfficeProfilePanel() {
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const profilePanel = el("profile-panel");
  if (!profilePanel) return;
  el("context-account-view")?.remove();
  el("admin-account-view")?.remove();

  let saved = {};
  try {
    const r = await authFetch(`${BACKEND_URL}/office/setup/get`);
    if (r.ok) { const d = await r.json(); saved = d.setup || {}; }
  } catch(e) { saved = JSON.parse(localStorage.getItem("hb_office_setup") || "{}"); }

  const wrap = document.createElement("div");
  wrap.id = "context-account-view";
  wrap.style.cssText = "padding:32px;max-width:680px;";
  wrap.innerHTML = `
    <div style="font-size:20px;font-weight:700;color:var(--ink);margin-bottom:4px;">My Office — Profile &amp; Identity</div>
    <div style="font-size:13px;color:var(--ink-4);margin-bottom:28px;line-height:1.55;">Your office identity is used for compliance disclosures and agent content oversight.</div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:14px;">Office Information</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Office Name</label>
        <input id="off-name" type="text" value="${_escHtml(saved.officeName||'')}" placeholder="e.g. Lundy Real Estate Group" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Brokerage Name</label>
        <input id="off-brokerage" type="text" value="${_escHtml(saved.brokerage||'')}" placeholder="e.g. eXp Realty" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Broker of Record</label>
        <input id="off-broker-of-record" type="text" value="${_escHtml(saved.brokerOfRecord||'')}" placeholder="Full legal name" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Office Phone</label>
        <input id="off-phone" type="tel" value="${_escHtml(saved.officePhone||'')}" placeholder="(303) 555-0100" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
      </div>
    </div>
    <div style="margin-bottom:28px;">
      <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Office Address</label>
      <input id="off-address" type="text" value="${_escHtml(saved.officeAddress||'')}" placeholder="123 Main St, Denver, CO 80202" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
    </div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:12px;">Agent Content Disclaimer</div>
    <div style="font-size:12px;color:var(--ink-4);margin-bottom:14px;line-height:1.6;">Controls how your office appears in compliance records on agent posts. The public post is never cluttered — only the PaperTrail™ PDF is affected unless you choose to replace the agent disclaimer.</div>
    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:14px;">
      ${[
        ["none",       "No office disclaimer — agents manage their own"],
        ["papertrail", "Include in PaperTrail™ PDF only — public post unaffected"],
        ["replace",    "Replace agent disclaimer on all posts — overrides individual agent disclaimers"],
      ].map(([val, label]) => `
        <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;font-size:13px;color:var(--ink-2);line-height:1.5;">
          <input type="radio" name="off-disclaimer-mode" value="${val}" ${(saved.disclaimerMode||'none')===val?'checked':''} onchange="toggleOfficeDisclaimer()" style="margin-top:2px;flex-shrink:0;" />
          ${label}
        </label>`).join("")}
    </div>
    <div id="off-disclaimer-wrap" style="display:${(saved.disclaimerMode&&saved.disclaimerMode!=='none')?'block':'none'};margin-bottom:28px;">
      <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Disclaimer Text <span style="font-weight:400;color:var(--ink-4);">(optional — leave blank for a smart default)</span></label>
      <textarea id="off-disclaimer-text" rows="3" placeholder="e.g. Brokerage: eXp Realty • Colorado License: EC12345678. Content approved by individual agent." style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:13px;outline:none;resize:vertical;">${_escHtml(saved.disclaimerText||'')}</textarea>
    </div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:16px;">Account Settings</div>
    <div style="display:flex;flex-direction:column;gap:14px;">
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Name</label><input id="ctx-profile-name" type="text" value="${_escHtml(user.agent_name||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Email</label><input id="ctx-profile-email" type="email" value="${_escHtml(user.email||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Notification Email</label><input id="ctx-profile-notif" type="email" value="${_escHtml(user.notification_email||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
    </div>
    <div id="ctx-account-msg" style="display:none;font-size:13px;font-weight:600;margin-top:12px;"></div>
    <button onclick="saveOfficeProfile()" style="width:100%;padding:13px;background:var(--blue);color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;margin-top:16px;">Save Office Profile</button>
    <div style="padding-top:20px;border-top:1px solid var(--border);margin-top:20px;">
      <div style="font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:10px;">Change Password</div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <input id="ctx-pw-current" type="password" placeholder="Current password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <input id="ctx-pw-new" type="password" placeholder="New password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <button onclick="saveContextPassword()" style="padding:11px;background:var(--surface);color:var(--ink);border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Update Password</button>
        <div id="ctx-pw-msg" style="display:none;font-size:13px;font-weight:600;"></div>
      </div>
    </div>
  `;
  profilePanel.appendChild(wrap);
}

function toggleOfficeDisclaimer() {
  const mode = document.querySelector('input[name="off-disclaimer-mode"]:checked')?.value || "none";
  const wrap = el("off-disclaimer-wrap");
  if (wrap) wrap.style.display = mode !== "none" ? "block" : "none";
}

async function saveOfficeProfile() {
  const msg = el("ctx-account-msg");
  const setup = {
    officeName:     el("off-name")?.value.trim()             || "",
    brokerage:      el("off-brokerage")?.value.trim()        || "",
    brokerOfRecord: el("off-broker-of-record")?.value.trim() || "",
    officePhone:    el("off-phone")?.value.trim()            || "",
    officeAddress:  el("off-address")?.value.trim()          || "",
    disclaimerMode: document.querySelector('input[name="off-disclaimer-mode"]:checked')?.value || "none",
    disclaimerText: el("off-disclaimer-text")?.value.trim()  || "",
  };
  await saveContextAccount();
  try {
    const r = await authFetch(`${BACKEND_URL}/office/setup/save`, { method:"POST", body:JSON.stringify({ setup }) });
    if (r.ok) {
      localStorage.setItem("hb_office_setup", JSON.stringify(setup));
      if (msg) { msg.textContent = "✓ Office profile saved"; msg.style.display = "block"; msg.style.color = "var(--green)"; setTimeout(() => { if(msg) msg.style.display = "none"; }, 2500); }
    } else {
      if (msg) { msg.textContent = "Save failed — try again."; msg.style.display = "block"; msg.style.color = "var(--red)"; }
    }
  } catch(e) {
    if (msg) { msg.textContent = "Save failed — try again."; msg.style.display = "block"; msg.style.color = "var(--red)"; }
  }
}

// ─── TEAM PROFILE ─────────────────────────────────────────────────────────────

async function renderTeamProfilePanel() {
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const profilePanel = el("profile-panel");
  if (!profilePanel) return;
  el("context-account-view")?.remove();
  el("admin-account-view")?.remove();

  let saved = {};
  try {
    const r = await authFetch(`${BACKEND_URL}/team/setup/get`);
    if (r.ok) { const d = await r.json(); saved = d.setup || {}; }
  } catch(e) { saved = JSON.parse(localStorage.getItem("hb_team_setup") || "{}"); }

  const wrap = document.createElement("div");
  wrap.id = "context-account-view";
  wrap.style.cssText = "padding:32px;max-width:680px;";
  wrap.innerHTML = `
    <div style="font-size:20px;font-weight:700;color:var(--ink);margin-bottom:4px;">My Team — Profile &amp; Identity</div>
    <div style="font-size:13px;color:var(--ink-4);margin-bottom:28px;line-height:1.55;">Your team identity is used for compliance disclosures on team member content.</div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:14px;">Team Information</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Team Name</label><input id="team-name" type="text" value="${_escHtml(saved.teamName||'')}" placeholder="e.g. The Lundy Group" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Brokerage Name</label><input id="team-brokerage" type="text" value="${_escHtml(saved.brokerage||'')}" placeholder="e.g. eXp Realty" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Team Lead Name</label><input id="team-lead-name" type="text" value="${_escHtml(saved.teamLeadName||user.agent_name||'')}" placeholder="Full name" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Team Phone</label><input id="team-phone" type="tel" value="${_escHtml(saved.teamPhone||'')}" placeholder="(303) 555-0100" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
    </div>
    <div style="margin-bottom:28px;"><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Team Website <span style="font-weight:400;color:var(--ink-4);">(optional)</span></label><input id="team-website" type="url" value="${_escHtml(saved.teamWebsite||'')}" placeholder="e.g. https://lundygroup.com" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:12px;">Team Content Disclaimer</div>
    <div style="font-size:12px;color:var(--ink-4);margin-bottom:14px;line-height:1.6;">Controls how your team appears in compliance records on team member posts.</div>
    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:14px;">
      ${[
        ["none",       "No team disclaimer — team members manage their own"],
        ["papertrail", "Include in PaperTrail™ PDF only — public post unaffected"],
        ["replace",    "Replace member disclaimer on all posts"],
      ].map(([val, label]) => `
        <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;font-size:13px;color:var(--ink-2);line-height:1.5;">
          <input type="radio" name="team-disclaimer-mode" value="${val}" ${(saved.disclaimerMode||'none')===val?'checked':''} onchange="toggleTeamDisclaimer()" style="margin-top:2px;flex-shrink:0;" />
          ${label}
        </label>`).join("")}
    </div>
    <div id="team-disclaimer-wrap" style="display:${(saved.disclaimerMode&&saved.disclaimerMode!=='none')?'block':'none'};margin-bottom:28px;">
      <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Disclaimer Text <span style="font-weight:400;color:var(--ink-4);">(optional)</span></label>
      <textarea id="team-disclaimer-text" rows="3" placeholder="e.g. The Lundy Group at eXp Realty • Colorado License: EC12345678." style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:13px;outline:none;resize:vertical;">${_escHtml(saved.disclaimerText||'')}</textarea>
    </div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:16px;">Account Settings</div>
    <div style="display:flex;flex-direction:column;gap:14px;">
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Name</label><input id="ctx-profile-name" type="text" value="${_escHtml(user.agent_name||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Email</label><input id="ctx-profile-email" type="email" value="${_escHtml(user.email||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Notification Email</label><input id="ctx-profile-notif" type="email" value="${_escHtml(user.notification_email||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
    </div>
    <div id="ctx-account-msg" style="display:none;font-size:13px;font-weight:600;margin-top:12px;"></div>
    <button onclick="saveTeamProfile()" style="width:100%;padding:13px;background:var(--blue);color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;margin-top:16px;">Save Team Profile</button>
    <div style="padding-top:20px;border-top:1px solid var(--border);margin-top:20px;">
      <div style="font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:10px;">Change Password</div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <input id="ctx-pw-current" type="password" placeholder="Current password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <input id="ctx-pw-new" type="password" placeholder="New password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <button onclick="saveContextPassword()" style="padding:11px;background:var(--surface);color:var(--ink);border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Update Password</button>
        <div id="ctx-pw-msg" style="display:none;font-size:13px;font-weight:600;"></div>
      </div>
    </div>
  `;
  profilePanel.appendChild(wrap);
}

function toggleTeamDisclaimer() {
  const mode = document.querySelector('input[name="team-disclaimer-mode"]:checked')?.value || "none";
  const wrap = el("team-disclaimer-wrap");
  if (wrap) wrap.style.display = mode !== "none" ? "block" : "none";
}

async function saveTeamProfile() {
  const msg = el("ctx-account-msg");
  const setup = {
    teamName:       el("team-name")?.value.trim()      || "",
    brokerage:      el("team-brokerage")?.value.trim() || "",
    teamLeadName:   el("team-lead-name")?.value.trim() || "",
    teamPhone:      el("team-phone")?.value.trim()     || "",
    teamWebsite:    el("team-website")?.value.trim()   || "",
    disclaimerMode: document.querySelector('input[name="team-disclaimer-mode"]:checked')?.value || "none",
    disclaimerText: el("team-disclaimer-text")?.value.trim() || "",
  };
  await saveContextAccount();
  try {
    const r = await authFetch(`${BACKEND_URL}/team/setup/save`, { method:"POST", body:JSON.stringify({ setup }) });
    if (r.ok) {
      localStorage.setItem("hb_team_setup", JSON.stringify(setup));
      if (msg) { msg.textContent = "✓ Team profile saved"; msg.style.display = "block"; msg.style.color = "var(--green)"; setTimeout(() => { if(msg) msg.style.display = "none"; }, 2500); }
    } else {
      if (msg) { msg.textContent = "Save failed — try again."; msg.style.display = "block"; msg.style.color = "var(--red)"; }
    }
  } catch(e) {
    if (msg) { msg.textContent = "Save failed — try again."; msg.style.display = "block"; msg.style.color = "var(--red)"; }
  }
}

// ─── HB MARKETING PROFILE ─────────────────────────────────────────────────────

function renderHBMarketingProfilePanel() {
  const user = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const profilePanel = el("profile-panel");
  if (!profilePanel) return;
  el("context-account-view")?.remove();
  el("admin-account-view")?.remove();

  const saved = JSON.parse(localStorage.getItem("hb_hb_setup") || "{}");
  const selectedNiches = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  const HB_NICHES = [
    "Independent Brokerages","Franchise Brokerages","Title Companies",
    "Mortgage Lenders","Real Estate Coaches","Team Leaders",
    "Property Managers","Real Estate Investors","Real Estate Attorneys",
    "Home Inspectors","Stagers & Photographers",
  ];

  const wrap = document.createElement("div");
  wrap.id = "context-account-view";
  wrap.style.cssText = "padding:32px;max-width:680px;";
  wrap.innerHTML = `
    <div style="font-size:20px;font-weight:700;color:var(--ink);margin-bottom:4px;">HB Marketing — Profile &amp; Identity</div>
    <div style="font-size:13px;color:var(--ink-4);margin-bottom:28px;line-height:1.55;">This identity shapes all HomeBridge marketing content. Completely separate from agent profiles.</div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:14px;">Company Identity</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:28px;">
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Company Name</label><input id="hbm-company" type="text" value="${_escHtml(saved.companyName||'The Home Bridge Group')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Primary Market / Region</label><input id="hbm-market" type="text" value="${_escHtml(saved.market||'')}" placeholder="e.g. Denver, Phoenix, Atlanta" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
    </div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:12px;">Who We Serve</div>
    <div style="font-size:12px;color:var(--ink-4);margin-bottom:12px;line-height:1.6;">Select the audience types HomeBridge content should target.</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:28px;" id="hbm-niches-grid">
      ${HB_NICHES.map(n => `
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;background:${selectedNiches.includes(n)?'var(--blue-dim)':'var(--surface)'};border:1.5px solid ${selectedNiches.includes(n)?'var(--blue)':'var(--border)'};border-radius:20px;padding:6px 14px;font-size:13px;font-weight:${selectedNiches.includes(n)?'600':'400'};color:${selectedNiches.includes(n)?'var(--blue)':'var(--ink-3)'};transition:all .15s;">
          <input type="checkbox" value="${_escHtml(n)}" ${selectedNiches.includes(n)?'checked':''} onchange="toggleHBMNiche(this)" style="display:none;" />
          ${_escHtml(n)}
        </label>`).join("")}
    </div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:14px;">Brand Voice &amp; Messaging</div>
    <div style="display:flex;flex-direction:column;gap:14px;margin-bottom:28px;">
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Why HomeBridge exists</label><textarea id="hbm-origin" rows="2" placeholder="e.g. Most agents have the talent — they just lack the system to show it consistently." style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:13px;outline:none;resize:vertical;">${_escHtml(saved.originStory||'')}</textarea></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">HomeBridge unfair advantage</label><textarea id="hbm-advantage" rows="2" placeholder="e.g. We find the story before any other agent knows it happened." style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:13px;outline:none;resize:vertical;">${_escHtml(saved.unfairAdvantage||'')}</textarea></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Brand Voice</label><textarea id="hbm-voice" rows="2" placeholder="e.g. Direct, confident, never corporate." style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:13px;outline:none;resize:vertical;">${_escHtml(saved.brandVoice||'')}</textarea></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
        <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Words to Avoid</label><input id="hbm-avoid" type="text" value="${_escHtml(saved.wordsAvoid||'')}" placeholder="e.g. disruptive, synergy" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
        <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Words to Prefer</label><input id="hbm-prefer" type="text" value="${_escHtml(saved.wordsPrefer||'')}" placeholder="e.g. real, local, authentic" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      </div>
    </div>

    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-3);margin-bottom:16px;">Account Settings</div>
    <div style="display:flex;flex-direction:column;gap:14px;">
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Name</label><input id="ctx-profile-name" type="text" value="${_escHtml(user.agent_name||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Email</label><input id="ctx-profile-email" type="email" value="${_escHtml(user.email||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
      <div><label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;">Notification Email</label><input id="ctx-profile-notif" type="email" value="${_escHtml(user.notification_email||'')}" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" /></div>
    </div>
    <div id="ctx-account-msg" style="display:none;font-size:13px;font-weight:600;margin-top:12px;"></div>
    <button onclick="saveHBMarketingProfile()" style="width:100%;padding:13px;background:var(--blue);color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;margin-top:16px;">Save HB Marketing Profile</button>
    <div style="padding-top:20px;border-top:1px solid var(--border);margin-top:20px;">
      <div style="font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:10px;">Change Password</div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <input id="ctx-pw-current" type="password" placeholder="Current password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <input id="ctx-pw-new" type="password" placeholder="New password" style="width:100%;padding:10px 12px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;outline:none;" />
        <button onclick="saveContextPassword()" style="padding:11px;background:var(--surface);color:var(--ink);border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Update Password</button>
        <div id="ctx-pw-msg" style="display:none;font-size:13px;font-weight:600;"></div>
      </div>
    </div>
  `;
  profilePanel.appendChild(wrap);
}

function toggleHBMNiche(checkbox) {
  const label = checkbox.closest("label");
  if (!label) return;
  const active = checkbox.checked;
  label.style.background  = active ? "var(--blue-dim)" : "var(--surface)";
  label.style.borderColor = active ? "var(--blue)"     : "var(--border)";
  label.style.color       = active ? "var(--blue)"     : "var(--ink-3)";
  label.style.fontWeight  = active ? "600"             : "400";
}

async function saveHBMarketingProfile() {
  const msg = el("ctx-account-msg");
  const selectedNiches = Array.from(
    document.querySelectorAll('#hbm-niches-grid input[type="checkbox"]:checked')
  ).map(cb => cb.value);
  const setup = {
    companyName:     el("hbm-company")?.value.trim()   || "The Home Bridge Group",
    market:          el("hbm-market")?.value.trim()    || "",
    primaryNiches:   selectedNiches,
    originStory:     el("hbm-origin")?.value.trim()    || "",
    unfairAdvantage: el("hbm-advantage")?.value.trim() || "",
    brandVoice:      el("hbm-voice")?.value.trim()     || "",
    wordsAvoid:      el("hbm-avoid")?.value.trim()     || "",
    wordsPrefer:     el("hbm-prefer")?.value.trim()    || "",
  };
  localStorage.setItem("hb_hb_setup", JSON.stringify(setup));
  await saveContextAccount();
  if (msg) { msg.textContent = "✓ HB Marketing profile saved"; msg.style.display = "block"; msg.style.color = "var(--green)"; setTimeout(() => { if(msg) msg.style.display = "none"; }, 2500); }
}

async function saveAdminAccount() {
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");
  if (!user) return;
  const name  = el("profile-name")?.value.trim()               || "";
  const email = el("profile-email")?.value.trim()              || "";
  const phone = el("profile-phone")?.value.trim()              || "";
  const notif = el("profile-notification-email")?.value.trim() || "";
  const msg   = el("admin-account-msg");
  try {
    const r = await authFetch(`${BACKEND_URL}/auth/profile`, {
      method:"POST", body:JSON.stringify({ agent_name:name, email, phone })
    });
    if (notif) {
      await authFetch(`${BACKEND_URL}/auth/profile/notification-email`, {
        method:"POST", body:JSON.stringify({ notification_email:notif })
      });
    }
    if (r.ok) {
      user.agent_name = name; user.email = email; user.phone = phone;
      if (notif) user.notification_email = notif;
      localStorage.setItem("hb_user", JSON.stringify(user));
      updateAvatar();
      if (msg) { msg.textContent = "✓ Saved"; msg.style.display = "block"; msg.style.color = "var(--green)"; setTimeout(() => { if(msg) msg.style.display = "none"; }, 2500); }
    }
  } catch(e) {
    if (msg) { msg.textContent = "Save failed — try again."; msg.style.display = "block"; msg.style.color = "var(--red)"; }
  }
}

async function saveAdminPassword() {
  const current = el("admin-pw-current")?.value || "";
  const next    = el("admin-pw-new")?.value     || "";
  const msg     = el("admin-pw-msg");
  if (!current || !next) { if(msg){msg.textContent="Enter both current and new password.";msg.style.display="block";msg.style.color="var(--red)";} return; }
  try {
    const r = await authFetch(`${BACKEND_URL}/auth/change-password`, {
      method:"POST", body:JSON.stringify({ current_password:current, new_password:next })
    });
    if (r.ok) {
      if(el("admin-pw-current")) el("admin-pw-current").value = "";
      if(el("admin-pw-new"))     el("admin-pw-new").value     = "";
      if(msg){msg.textContent="✓ Password updated";msg.style.display="block";msg.style.color="var(--green)";setTimeout(()=>{if(msg)msg.style.display="none";},2500);}
    } else {
      const d = await r.json().catch(()=>({}));
      if(msg){msg.textContent=d.detail||"Incorrect current password.";msg.style.display="block";msg.style.color="var(--red)";}
    }
  } catch(e) {
    if(msg){msg.textContent="Error — try again.";msg.style.display="block";msg.style.color="var(--red)";}
  }
}

function renderProfilePanel() {
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");
  const saved = getSaved();
  if (!user) return;

  // Always clean up admin/context account views before rendering — prevents duplicates
  el("admin-account-view")?.remove();
  el("context-account-view")?.remove();
  el("org-profile-view")?.remove();

  // Always restore agent content visibility in case we're switching from admin context
  const agentContent = el("profile-agent-content");
  if (agentContent) agentContent.style.display = "";

  // Load billing status every time profile panel opens
  loadBillingStatus();

  // Admin/super_admin context — account management only, no content identity
  const ctx = getViewContext();
  if (ctx === "super_admin" || ctx === "admin") {
    renderAdminAccountPanel();
    return;
  }
  // Office context — full office profile
  if (ctx === "office" || ctx === "broker") {
    if (agentContent) agentContent.style.display = "none";
    renderOfficeProfilePanel();
    return;
  }
  // Team context — full team profile
  if (ctx === "team") {
    if (agentContent) agentContent.style.display = "none";
    renderTeamProfilePanel();
    return;
  }
  // HB Marketing context — HomeBridge brand identity
  if (ctx === "marketing") {
    if (agentContent) agentContent.style.display = "none";
    renderHBMarketingProfilePanel();
    return;
  }
  // Partner context — account settings only
  if (ctx === "partner") {
    if (agentContent) agentContent.style.display = "none";
    renderContextAccountPanel("Partner Program", "Your agent profile and content identity live in My Work.");
    return;
  }

  const isGS   = _profileMode === "guided";
  const guided = el("profile-guided");
  const full   = el("profile-full");
  if (guided) guided.style.display = isGS ? "block" : "none";
  if (full)   full.style.display   = isGS ? "none"  : "block";

  if (isGS) {
    // Guided mode — pre-fill the 3 fields
    if (el("guided-name"))       el("guided-name").value       = user.agent_name || saved.agentName || "";
    if (el("guided-brokerage"))  el("guided-brokerage").value  = user.brokerage  || saved.brokerage  || "";
    if (el("guided-market"))     el("guided-market").value     = saved.market    || "";
    if (el("guided-disclaimer")) el("guided-disclaimer").value = getDisclaimer() || "";
    return;
  }

  // Full mode — populate all fields
  // Show journey wayfinding only if arriving from Getting Started
  const journeyHint = el("profile-journey-hint");
  const nextRow     = el("profile-next-row");
  if (journeyHint) journeyHint.style.display = _profileFromGS ? "block" : "none";
  if (nextRow)     nextRow.style.display     = _profileFromGS ? "flex"  : "none";
  // Open Account accordion by default if no data yet, so screen isn't blank
  const acctBody = el("acc-body-account");
  const acctChev = el("acc-chevron-account");
  if (acctBody && acctBody.style.display === "none" && !(user.agent_name)) {
    acctBody.style.display = "block";
    if (acctChev) acctChev.classList.add("open");
  }
  if (el("profile-name"))      el("profile-name").value      = user.agent_name || "";
  if (el("profile-brokerage")) el("profile-brokerage").value = user.brokerage  || "";
  if (el("profile-email"))     el("profile-email").value     = user.email      || "";
  if (el("profile-phone"))     el("profile-phone").value     = user.phone      || "";
  if (el("profile-notification-email")) el("profile-notification-email").value = user.notification_email || "";

  // Restore SMS consent state and frequency preference
  const smsBox  = el("sms-consent-checkbox");
  const smsFreq = el("sms-frequency-section");
  if (smsBox) {
    smsBox.checked = !!(saved.smsConsentGiven && user.phone);
    if (smsFreq) smsFreq.style.display = smsBox.checked ? "block" : "none";
    // Set saved frequency
    if (saved.smsFrequency) {
      const freqInput = document.querySelector(`input[name='sms-frequency'][value='${saved.smsFrequency}']`);
      if (freqInput) freqInput.checked = true;
    }
    // Wire toggle — show/hide frequency section when consent changes
    smsBox.onchange = function() {
      if (smsFreq) smsFreq.style.display = this.checked ? "block" : "none";
      autoSaveAccountInfo();
    };
  }
  // CTA + Voice Profile fields
  renderCtaMethods();
  if (el("origin-story"))           el("origin-story").value           = saved.originStory          || "";
  if (el("unfair-advantage"))       el("unfair-advantage").value       = saved.unfairAdvantage      || "";
  if (el("signature-perspective"))  el("signature-perspective").value  = saved.signaturePerspective || "";
  if (el("not-for-client"))         el("not-for-client").value         = saved.notForClient         || "";
  // Recruiting fields
  if (el("recruiting-enabled")) {
    el("recruiting-enabled").checked = saved.recruitingEnabled || false;
    const field = el("recruiting-cta-field");
    if (field) field.style.display = saved.recruitingEnabled ? "block" : "none";
  }
  if (el("recruiting-cta"))     el("recruiting-cta").value     = saved.recruitingCta || "";
  const mls = JSON.parse(localStorage.getItem("hb_mls") || "[]");
  if (el("profile-mls-1")) el("profile-mls-1").value = mls[0] || "";
  if (el("profile-mls-2")) el("profile-mls-2").value = mls[1] || "";
  if (el("profile-mls-3")) el("profile-mls-3").value = mls[2] || "";
  if (el("profile-disclaimer")) el("profile-disclaimer").value = getDisclaimer();
  if (el("business-name") && saved.businessName) el("business-name").value = saved.businessName;
  if (el("market")        && saved.market)        el("market").value        = saved.market;
  if (el("short-bio")     && saved.shortBio)      el("short-bio").value     = saved.shortBio;
  if (el("brand-voice")   && saved.brandVoice)    el("brand-voice").value   = saved.brandVoice;
  if (el("words-avoid")   && saved.wordsAvoid)    el("words-avoid").value   = saved.wordsAvoid;
  if (el("words-prefer")  && saved.wordsPrefer)   el("words-prefer").value  = saved.wordsPrefer;
  renderServiceAreaChips(Array.isArray(saved.serviceAreas) ? saved.serviceAreas : []);
  loadDesignations(saved);
  loadLanguagePref();
  loadPlatformPrefs(saved);
  wireDesignationCheckboxes();
  wireLangOptions();
  updateProfileCompleteness();
  wireProfileAutosave();
  // Load brokerage logo preview
  loadBrokerageLogoPreview();
  // Marketing context — hide agent-specific fields, relabel for platform company
  if (ctx === "marketing") _applyMarketingProfileContext();
  // Render Jordan card at bottom of profile — agent context only
  if (ctx === "agent" || ctx === "my_work" || (!ctx)) renderJordanProfileCard();
}

el("guided-continue-btn")?.addEventListener("click", async () => {
  const name       = el("guided-name")?.value.trim()       || "";
  const brokerage  = el("guided-brokerage")?.value.trim()  || "";
  const market     = el("guided-market")?.value.trim()     || "";
  const disclaimer = el("guided-disclaimer")?.value.trim() || "";
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  if (!name) { el("guided-name").focus(); return; }
  // Save to localStorage immediately
  const saved = getSaved();
  saved.agentName = name; saved.brokerage = brokerage;
  saved.market = market || saved.market;
  if (disclaimer) saved.disclaimer = disclaimer;
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  if (disclaimer) localStorage.setItem("hb_disclaimer", disclaimer);
  const user = JSON.parse(localStorage.getItem("hb_user")||"{}");
  user.agent_name = name; user.brokerage = brokerage;
  localStorage.setItem("hb_user", JSON.stringify(user));
  gsMarkDone(1);
  if (isDemo) {
    showMsg("profile-guided-success", "✓ Saved — complete your profile below.");
    setTimeout(() => {
      hideMsg("profile-guided-success");
      _profileMode = "full";
      renderProfilePanel();
      // Open disclaimer accordion so agent sees what to complete next
      setTimeout(() => {
        const b = document.getElementById("acc-body-disclaimer");
        if (b && b.style.display === "none") toggleAccordion("disclaimer");
      }, 200);
    }, 800);
    return;
  }
  // Real user: save to backend then stay on profile in full mode
  const btn = el("guided-continue-btn"); btn.disabled = true; btn.textContent = "Saving…";
  try {
    const res = await authFetch(`${BACKEND_URL}/auth/profile`, { method:"POST", body:JSON.stringify({ agent_name:name, brokerage, email:user.email, phone:user.phone||"" }) });
    if (res.ok) {
      await _setupSave(saved);
    }
  } catch(e) {}
  finally { btn.disabled = false; btn.textContent = "Save & continue →"; }
  _profileMode = "full";
  renderProfilePanel();
  showMsg("profile-guided-success", "✓ Saved — complete your profile below.");
  setTimeout(() => hideMsg("profile-guided-success"), 2500);
  // Open disclaimer section next
  setTimeout(() => {
    const b = document.getElementById("acc-body-disclaimer");
    if (b && b.style.display === "none") toggleAccordion("disclaimer");
  }, 300);
});

// save-profile-btn removed — account info now autosaves via autoSaveAccountInfo()
// wired in wireProfileAutosave() which is called from renderProfilePanel().

el("cta-add-method-btn")?.addEventListener("click", _ctaAddMethod);

el("save-password-btn")?.addEventListener("click", async () => {
  const btn = el("save-password-btn"); hideMsg("profile-error");
  if (localStorage.getItem("hb_demo_mode") === "true") {
    showMsg("profile-success", "This is a demo — create a free account to save your settings.");
    return;
  }
  const current  = el("profile-current-password")?.value || "";
  const password = el("profile-new-password")?.value || "";
  if (!current || !password) { showMsg("profile-error","Both password fields are required.",true); return; }
  if (password.length < 8)   { showMsg("profile-error","New password must be at least 8 characters.",true); return; }
  btn.disabled = true; btn.textContent = "Updating…";
  try {
    const res  = await authFetch(`${BACKEND_URL}/auth/change-password`, { method:"POST", body:JSON.stringify({ current_password:current, new_password:password }) });
    const data = await res.json();
    if (!res.ok) { showMsg("profile-error",data.detail||"Password update failed.",true); return; }
    showMsg("profile-success","✓ Password updated.");
    el("profile-current-password").value = ""; el("profile-new-password").value = "";
  } catch(e) { showMsg("profile-error","Could not reach server.",true); }
  finally { btn.disabled = false; btn.textContent = "Update Password"; }
});

// save-socials-btn removed — social handles now autosave via wireProfileAutosave()



el("save-identity-btn")?.addEventListener("click", async () => {
  // "Save my voice" — scoped to Zone of Greatness fields only.
  // All other identity fields (market, state, bio, CTA, etc.) autosave on blur.
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  const saved  = getSaved();

  const origin  = el("origin-story")?.value.trim()          || "";
  const sigBel  = el("signature-perspective")?.value.trim() || "";
  const unfair  = el("unfair-advantage")?.value.trim()      || "";
  const notFor  = el("not-for-client")?.value.trim()        || "";

  // Save whatever is filled in — never block a partial save
  // These fields accumulate over time as the agent builds their voice profile
  if (origin)  saved.originStory          = origin;
  if (sigBel)  saved.signaturePerspective = sigBel;
  if (unfair)  saved.unfairAdvantage      = unfair;
  if (notFor)  saved.notForClient         = notFor;

  // Also preserve any existing values if field is currently blank
  // (don't overwrite a saved value with an empty string)
  if (!origin  && saved.originStory)          { /* keep existing */ }
  if (!sigBel  && saved.signaturePerspective) { /* keep existing */ }
  if (!unfair  && saved.unfairAdvantage)      { /* keep existing */ }
  if (!notFor  && saved.notForClient)         { /* keep existing */ }

  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  gsMarkDone(1);
  const identityMsg = el("identity-saved-msg");
  if (identityMsg) { identityMsg.style.display = "inline"; setTimeout(() => identityMsg.style.display = "none", 2500); }

  if (!isDemo) {
    _setupSave(saved);
  }

  const hasContent = Array.isArray(_cachedLibrary) && _cachedLibrary.length > 0;
  if (!hasContent) {
    setTimeout(() => navigateTo("content-engine-panel"), 1400);
  }
});

// save-language-btn removed — language now autosaves via wireProfileAutosave()



// ─────────────────────────────────────────────
// SECTION 19: PLATFORM TOGGLES
// ─────────────────────────────────────────────
function loadPlatformPrefs(saved) {
  const platforms = Array.isArray(saved?.platforms) ? saved.platforms : [];
  const oauthConns = JSON.parse(localStorage.getItem("hb_oauth_connections") || "{}");
  PLATFORM_META.forEach(p => {
    const activeEl   = el(`plat-active-${p.id}`);
    const handleEl   = el(`social-${p.id}`);
    const handleRow  = el(`plat-handle-wrap-${p.id}`);
    const connectRow = el(`plat-connect-wrap-${p.id}`);
    const saved_p    = platforms.find(x => x.id === p.id);
    const isOAuthConnected = OAUTH_PLATFORMS.includes(p.id) && oauthConns[p.id]?.connected;
    if (activeEl)   activeEl.checked             = !!saved_p;
    if (handleEl && saved_p?.handle) handleEl.value = saved_p.handle;
    if (handleRow)  handleRow.style.display       = saved_p ? "flex"  : "none";
    // Only show the Connect button row if active AND not already OAuth-connected
    if (connectRow) connectRow.style.display      = (saved_p && !isOAuthConnected) ? "block" : "none";
  });
}
function savePlatformPrefs() {
  const active = getActivePlatforms();
  const saved  = getSaved();
  saved.platforms = active.map(p => ({ id:p.id, name:p.name, handle:p.handle }));
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  _setupSave(saved);
}
// Show forgot password hint
function showForgotPasswordHint() {
  const hint = document.getElementById("forgot-password-hint");
  if (hint) hint.style.display = "block";
}

// Wire platform toggles
document.querySelectorAll(".platform-active-toggle").forEach(toggle => {
  toggle.addEventListener("change", () => {
    const row        = toggle.closest(".platform-row");
    const id         = row?.dataset.platform;
    const handleRow  = id ? el(`plat-handle-wrap-${id}`) : null;
    const connectRow = id ? el(`plat-connect-wrap-${id}`) : null;
    if (handleRow)  handleRow.style.display  = toggle.checked ? "flex" : "none";
    if (connectRow) connectRow.style.display = toggle.checked ? "block" : "none";
    savePlatformPrefs();
  });
});

// Disclaimer
// save-disclaimer-btn removed — disclaimer now autosaves via wireProfileAutosave()



// ─────────────────────────────────────────────
// SECTION 20: DESIGNATIONS, SERVICE AREAS, LANGUAGE
// ─────────────────────────────────────────────
function loadDesignations(saved) {
  const desigs = Array.isArray(saved.designations) ? saved.designations : [];
  // Sync the checkbox grid
  document.querySelectorAll(".desig-cb").forEach(cb => {
    const isOn = desigs.includes(cb.value);
    cb.checked = isOn;
    const label = cb.closest(".designation-chip");
    if (label) label.classList.toggle("active", isOn);
  });
  // Sync custom chips container
  const container = el("custom-designations-chips");
  if (!container) return;
  const STANDARD = ["ABR","CRS","GRI","SRES","CIPS","GREEN","SRS","MRP","PSA","e-PRO","AHWD","RSPS"];
  const custom = desigs.filter(d => !STANDARD.includes(d));
  container.innerHTML = "";
  custom.forEach(d => {
    const chip = document.createElement("div");
    chip.className = "chip selected"; chip.textContent = d + " ✕";
    chip.onclick = () => {
      const cur = getSaved(); cur.designations = (cur.designations||[]).filter(x=>x!==d);
      localStorage.setItem(getSetupKey(), JSON.stringify(cur));
      loadDesignations(cur);
    };
    container.appendChild(chip);
  });
}

function wireDesignationCheckboxes() {
  // Use onclick on the label — avoids display:none change-event issues across browsers
  document.querySelectorAll(".designation-chip").forEach(label => {
    // Remove any prior listener to avoid duplicates on re-render
    const fresh = label.cloneNode(true);
    label.parentNode.replaceChild(fresh, label);
    fresh.addEventListener("click", (e) => {
      e.preventDefault();
      const cb = fresh.querySelector(".desig-cb");
      if (!cb) return;
      cb.checked = !cb.checked;
      fresh.classList.toggle("active", cb.checked);
      const STANDARD = ["ABR","CRS","GRI","SRES","CIPS","GREEN","SRS","MRP","PSA","e-PRO","AHWD","RSPS"];
      const cur = getSaved();
      const custom = (cur.designations||[]).filter(d => !STANDARD.includes(d));
      const checked = Array.from(document.querySelectorAll(".desig-cb:checked")).map(c => c.value);
      cur.designations = [...checked, ...custom];
      localStorage.setItem(getSetupKey(), JSON.stringify(cur));
    });
  });
}
el("add-designation-btn")?.addEventListener("click", () => {
  const input = el("designation-input"); if (!input) return;
  const v = input.value.trim().toUpperCase();
  if (!v) return;
  const saved = getSaved();
  saved.designations = [...new Set([...(saved.designations||[]),v])];
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  loadDesignations(saved); input.value = "";
});

function renderServiceAreaChips(areas) {
  const container = el("service-areas-chips"); if (!container) return;
  container.innerHTML = areas.map(a => `<div class="chip selected" data-area="${a}">${a} <span onclick="removeServiceArea('${a}')">✕</span></div>`).join("");
}
function removeServiceArea(area) {
  const saved = getSaved();
  saved.serviceAreas = (saved.serviceAreas||[]).filter(a=>a!==area);
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  renderServiceAreaChips(saved.serviceAreas);
}
function addServiceAreaFromInput() {
  const input = el("service-area-input"); if (!input) return;
  const v = input.value.trim(); if (!v) return;
  const saved = getSaved();
  saved.serviceAreas = [...new Set([...(saved.serviceAreas||[]),v])];
  localStorage.setItem(getSetupKey(), JSON.stringify(saved));
  renderServiceAreaChips(saved.serviceAreas); input.value = "";
}
el("service-area-add-btn")?.addEventListener("click", addServiceAreaFromInput);
el("service-area-input")?.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); addServiceAreaFromInput(); } });

function loadLanguagePref() {
  const v = getLanguagePref();
  // Sync radio buttons and .active class on language-option labels
  document.querySelectorAll("input[name='content-language']").forEach(radio => {
    radio.checked = (radio.value === v);
    const label = radio.closest(".language-option");
    if (label) label.classList.toggle("active", radio.value === v);
  });
}

function wireLangOptions() {
  document.querySelectorAll(".language-option").forEach(label => {
    const fresh = label.cloneNode(true);
    label.parentNode.replaceChild(fresh, label);
    fresh.addEventListener("click", (e) => {
      e.preventDefault();
      const radio = fresh.querySelector("input[type='radio']");
      if (!radio) return;
      radio.checked = true;
      document.querySelectorAll(".language-option").forEach(l => l.classList.remove("active"));
      fresh.classList.add("active");
    });
  });
}

// ─────────────────────────────────────────────
// SECTION 21: NICHE CHIPS — SETUP PANEL
// ─────────────────────────────────────────────
// ─────────────────────────────────────────────
// NICHE ACCORDION — replaces tab/chip system
// Each category is a collapsible row.
// Niches appear as checkboxes inside.
// Sub-specialties appear inline below each checked niche.
// ─────────────────────────────────────────────

let _nicheAccordionOpen = {}; // tracks which categories are expanded

function renderNicheAccordion() {
  const container = el("niche-accordion");
  if (!container) return;

  const isMarketing    = getViewContext() === "marketing";
  const categories     = isMarketing ? NICHE_CATEGORIES_B2B : NICHE_CATEGORIES;
  const totalSelected  = selectedPrimaryNiches.length + getCustomNiches().length;

  // ── Soft guidance counter ──
  const hint = el("niche-count-hint");
  if (hint) {
    if (totalSelected === 0) {
      hint.style.display = "none";
    } else if (totalSelected <= 4) {
      hint.style.display = "block";
      hint.style.background = "var(--green-dim,#f0fdf4)";
      hint.style.color = "var(--green,#15803d)";
      hint.style.border = "1px solid rgba(21,128,61,0.2)";
      hint.textContent = `${totalSelected} niche${totalSelected===1?"":"s"} selected — solid foundation for focused content.`;
    } else if (totalSelected <= 6) {
      hint.style.display = "block";
      hint.style.background = "var(--amber-dim,#fffbeb)";
      hint.style.color = "var(--amber,#d97706)";
      hint.style.border = "1px solid rgba(217,119,6,0.2)";
      hint.textContent = `${totalSelected} niches selected — consider focusing on your strongest areas for sharper content.`;
    } else {
      hint.style.display = "block";
      hint.style.background = "#fff7f7";
      hint.style.color = "#b91c1c";
      hint.style.border = "1px solid rgba(185,28,28,0.15)";
      hint.textContent = `${totalSelected} niches selected — more niches means more content but less depth. Less is often more.`;
    }
  }

  container.innerHTML = "";

  Object.entries(categories).forEach(([cat, niches]) => {
    const selectedInCat = niches.filter(n => selectedPrimaryNiches.includes(n));
    const isOpen = _nicheAccordionOpen[cat] ?? (selectedInCat.length > 0);

    // ── Category row ──
    const catRow = document.createElement("div");
    catRow.style.cssText = `
      border:1.5px solid ${selectedInCat.length ? "var(--blue,#1749c9)" : "var(--border)"};
      border-radius:10px;
      overflow:hidden;
      transition:border-color .15s;
    `;

    // Header
    const header = document.createElement("div");
    header.style.cssText = `
      display:flex;align-items:center;justify-content:space-between;
      padding:12px 16px;cursor:pointer;
      background:${selectedInCat.length ? "var(--blue-dim,#eef2fb)" : "var(--surface,#fff)"};
      transition:background .15s;
      user-select:none;
    `;

    const left = document.createElement("div");
    left.style.cssText = "display:flex;align-items:center;gap:10px;";

    const catLabel = document.createElement("div");
    catLabel.style.cssText = `font-size:13px;font-weight:${selectedInCat.length?"700":"600"};color:${selectedInCat.length?"var(--blue,#1749c9)":"var(--ink)"};`;
    catLabel.textContent = cat;

    const badge = document.createElement("div");
    badge.style.cssText = `font-size:11px;font-weight:600;padding:2px 8px;border-radius:10px;
      background:${selectedInCat.length?"var(--blue,#1749c9)":"var(--bg-sunken,#f5f5f3)"};
      color:${selectedInCat.length?"#fff":"var(--ink-3)"};
      display:${selectedInCat.length?"inline-block":"none"};`;
    badge.textContent = `${selectedInCat.length} selected`;

    left.appendChild(catLabel);
    left.appendChild(badge);

    const chevron = document.createElement("div");
    chevron.style.cssText = `font-size:12px;color:var(--ink-3);transition:transform .2s;transform:${isOpen?"rotate(180deg)":"rotate(0deg)"};`;
    chevron.textContent = "▾";

    header.appendChild(left);
    header.appendChild(chevron);

    // Body
    const body = document.createElement("div");
    body.style.cssText = `
      display:${isOpen?"block":"none"};
      padding:12px 16px 16px;
      background:var(--surface,#fff);
      border-top:1px solid var(--border);
    `;

    niches.forEach(niche => {
      const isChecked = selectedPrimaryNiches.includes(niche);
      const subs      = NICHE_DATA[niche] || [];

      // Niche row
      const nicheWrap = document.createElement("div");
      nicheWrap.style.cssText = "margin-bottom:4px;";

      const nicheLabel = document.createElement("label");
      nicheLabel.style.cssText = `
        display:flex;align-items:center;gap:10px;padding:8px 10px;
        border-radius:8px;cursor:pointer;
        background:${isChecked?"var(--blue-dim,#eef2fb)":"transparent"};
        transition:background .12s;
      `;
      nicheLabel.onmouseover = () => { if (!isChecked) nicheLabel.style.background = "var(--bg-sunken,#f5f5f3)"; };
      nicheLabel.onmouseout  = () => { if (!isChecked) nicheLabel.style.background = "transparent"; };

      const cb = document.createElement("input");
      cb.type    = "checkbox";
      cb.checked = isChecked;
      cb.style.cssText = "width:16px;height:16px;cursor:pointer;flex-shrink:0;accent-color:var(--blue,#1749c9);";

      const nicheName = document.createElement("div");
      nicheName.style.cssText = `font-size:13px;font-weight:${isChecked?"600":"400"};color:${isChecked?"var(--blue,#1749c9)":"var(--ink)"};`;
      nicheName.textContent = niche;

      nicheLabel.appendChild(cb);
      nicheLabel.appendChild(nicheName);
      nicheWrap.appendChild(nicheLabel);

      // Sub-specialties — inline below when checked
      const subsWrap = document.createElement("div");
      subsWrap.style.cssText = `
        display:${isChecked&&subs.length?"block":"none"};
        margin:4px 0 8px 26px;
        padding:10px 12px;
        background:var(--bg-sunken,#f8f8f6);
        border-radius:8px;
        border-left:2px solid var(--blue-border,rgba(23,73,201,0.2));
      `;

      if (subs.length) {
        const subsLabel = document.createElement("div");
        subsLabel.style.cssText = "font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-4);margin-bottom:4px;";
        subsLabel.textContent = "Specialties — all selected. Tap to deselect any that don't apply.";
        subsWrap.appendChild(subsLabel);

        const subsGrid = document.createElement("div");
        subsGrid.style.cssText = "display:flex;flex-wrap:wrap;gap:5px;";

        subs.forEach(sub => {
          const subChip = document.createElement("div");
          const subSelected = selectedSubNiches.includes(sub);
          subChip.style.cssText = `
            font-size:11px;font-weight:${subSelected?"600":"400"};
            padding:4px 10px;border-radius:20px;cursor:pointer;
            border:1px solid ${subSelected?"var(--blue,#1749c9)":"var(--border)"};
            background:${subSelected?"var(--blue,#1749c9)":"var(--surface,#fff)"};
            color:${subSelected?"#fff":"var(--ink-3)"};
            transition:all .12s;
            display:flex;align-items:center;gap:4px;
          `;
          subChip.innerHTML = `${subSelected?'<span style="font-size:10px;">✓</span>':''}<span>${sub}</span>`;
          subChip.addEventListener("click", () => {
            if (selectedSubNiches.includes(sub)) {
              selectedSubNiches = selectedSubNiches.filter(s => s !== sub);
            } else {
              selectedSubNiches.push(sub);
            }
            renderNicheAccordion();
          });
          subsGrid.appendChild(subChip);
        });
        subsWrap.appendChild(subsGrid);
      }

      nicheWrap.appendChild(subsWrap);

      // Checkbox change handler
      cb.addEventListener("change", () => {
        if (cb.checked) {
          if (!selectedPrimaryNiches.includes(niche)) {
            selectedPrimaryNiches.push(niche);
            // Auto-select all sub-specialties on first add
            (NICHE_DATA[niche]||[]).forEach(s => { if (!selectedSubNiches.includes(s)) selectedSubNiches.push(s); });
          }
        } else {
          selectedPrimaryNiches = selectedPrimaryNiches.filter(n => n !== niche);
          selectedSubNiches = selectedSubNiches.filter(s => !(NICHE_DATA[niche]||[]).includes(s));
        }
        renderNicheAccordion();
        renderScheduleUI();
      });

      body.appendChild(nicheWrap);
    });

    // Toggle accordion
    header.addEventListener("click", () => {
      _nicheAccordionOpen[cat] = !isOpen;
      renderNicheAccordion();
    });

    catRow.appendChild(header);
    catRow.appendChild(body);
    container.appendChild(catRow);
  });
}

// Keep these as thin wrappers so all existing call sites work unchanged
function renderPrimaryNicheChips() { renderNicheAccordion(); }
function renderSubNicheChips()     { renderNicheAccordion(); }

// Toggle the custom niche input row
function toggleCustomNicheInput() {
  const row = el("custom-niche-add-row");
  const toggle = el("custom-niche-toggle");
  if (!row) return;
  const isVisible = row.style.display !== "none";
  row.style.display = isVisible ? "none" : "flex";
  if (toggle) toggle.style.display = isVisible ? "" : "none";
  if (!isVisible) setTimeout(() => el("custom-niche-input")?.focus(), 50);
}

function renderCustomNicheChips() {
  const container = el("custom-niche-chips"); if (!container) return;
  container.innerHTML = "";
  getCustomNiches().forEach(niche => {
    const chip = document.createElement("div");
    chip.className = "chip selected"; chip.textContent = niche + " ✕";
    chip.addEventListener("click", () => { localStorage.setItem("hb_custom_niches", JSON.stringify(getCustomNiches().filter(n=>n!==niche))); renderCustomNicheChips(); });
    container.appendChild(chip);
  });
}
// Wire custom niche add button
function addCustomNiche() {
  const input = el("custom-niche-input"); if (!input) return;
  const v = input.value.trim();
  if (!v || v.includes("@")) return;
  const custom = [...new Set([...getCustomNiches(), v])];
  localStorage.setItem("hb_custom_niches", JSON.stringify(custom));
  renderCustomNicheChips(); renderSubNicheChips();
  input.value = "";
}
el("custom-niche-add-btn")?.addEventListener("click", addCustomNiche);
el("custom-niche-input")?.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); addCustomNiche(); } });

function renderNicheSelector() {
  const container = el("niche-selector-chips"); if (!container) return;
  container.innerHTML = "";
  // Always read from saved data so newly saved niches appear immediately
  const saved = getSaved();
  const savedNiches = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  const merged = [...new Set([...selectedPrimaryNiches, ...savedNiches])];
  selectedPrimaryNiches = merged;
  const allNiches = [...new Set([...selectedPrimaryNiches, ...getCustomNiches()])];
  // Hide the redundant bottom niche selector — niche selection is handled by
  // the identity summary pills at the top of the content engine panel.
  const group = el("niche-selector-group");
  if (group) group.style.display = "none";
  if (!allNiches.length) { container.innerHTML = '<div style="font-size:13px;color:var(--muted);">No niches set. Go to Focus to add your primary niches.</div>'; return; }
  allNiches.forEach(niche => {
    const chip = document.createElement("div");
    chip.className = "chip" + (activeNicheForGenerate===niche?" selected":"");
    chip.textContent = niche;
    chip.addEventListener("click", () => {
      activeNicheForGenerate = (activeNicheForGenerate===niche) ? null : niche;
      renderNicheSelector();
      populateSituationDropdown(activeNicheForGenerate||allNiches[0]||null);
      updatePersonaDropdown(activeNicheForGenerate||allNiches[0]||null);
    });
    container.appendChild(chip);
  });
}



// ─────────────────────────────────────────────
// SECTION 22: CONTENT SCHEDULE
// ─────────────────────────────────────────────
async function loadSchedules() {
  try {
    const res = await authFetch(`${BACKEND_URL}/schedules`);
    if (!res.ok) return;
    const data = await res.json();
    _schedules = {};
    (data.schedules||[]).forEach(s => { _schedules[s.niche] = s; });
  } catch(e) {}
}
async function renderScheduleUI() {
  const container = el("schedule-list"); if (!container) return;
  if (localStorage.getItem("hb_demo_mode") === "true") {
    container.innerHTML = '<div style="font-size:12px;color:var(--muted);">Schedule not available in demo mode.</div>';
    return;
  }
  await loadSchedules();
  const saved     = getSaved();
  // ONLY show niches that are currently saved in the agent's identity.
  // Do NOT merge selectedPrimaryNiches (in-memory, stale) or old schedule records.
  // If a niche was removed from identity, its schedule row is ignored here.
  const allNiches = [...new Set([...(saved.primaryNiches||[]), ...getCustomNiches()])];
  if (!allNiches.length) {
    container.innerHTML = '<div style="font-size:12px;color:var(--muted);font-style:italic;">Select your niches above — then set your schedule here.</div>';
    return;
  }

  const DAYS = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

  container.innerHTML = "";

  allNiches.forEach(niche => {
    const sched   = _schedules[niche] || {};
    const freq    = sched.frequency  || "weekly";
    const time    = sched.timeOfDay  || "08:00";
    const isOff   = !sched.active && sched.active !== undefined ? true : (freq === "off" || !sched.frequency);
    const savedDays = (() => {
      try { return JSON.parse(sched.dayOfWeek || "[]"); } catch(e) { return sched.dayOfWeek ? [sched.dayOfWeek] : []; }
    })();

    const row = document.createElement("div");
    row.style.cssText = `
      background:#fff;
      border:1.5px solid ${isOff?"var(--border)":"var(--blue-border,rgba(23,73,201,0.25))"};
      border-radius:12px;
      padding:14px 16px;
      margin-bottom:10px;
      transition:border-color .15s;
    `;

    // Header row — niche name + on/off toggle
    const header = document.createElement("div");
    header.style.cssText = "display:flex;align-items:center;justify-content:space-between;margin-bottom:${isOff?'0':'14px'};";

    const nameWrap = document.createElement("div");
    const nicheName = document.createElement("div");
    nicheName.style.cssText = `font-size:13px;font-weight:700;color:${isOff?"var(--ink-3)":"var(--blue)"};`;
    nicheName.textContent = niche;
    const nextRun = document.createElement("div");
    nextRun.style.cssText = "font-size:11px;color:var(--muted);margin-top:2px;";
    nextRun.textContent = !isOff && sched.nextRun
      ? `Next: ${new Date(sched.nextRun).toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})}`
      : isOff ? "Auto-generation off" : "Not yet scheduled";
    nameWrap.appendChild(nicheName);
    nameWrap.appendChild(nextRun);

    // Toggle switch
    const toggleWrap = document.createElement("label");
    toggleWrap.style.cssText = "display:flex;align-items:center;gap:8px;cursor:pointer;flex-shrink:0;";
    toggleWrap.title = isOff ? "Turn on auto-generation" : "Turn off auto-generation";
    const toggleInput = document.createElement("input");
    toggleInput.type = "checkbox";
    toggleInput.checked = !isOff;
    toggleInput.style.cssText = "width:16px;height:16px;accent-color:var(--blue,#1749c9);cursor:pointer;";
    const toggleLabel = document.createElement("span");
    toggleLabel.style.cssText = `font-size:12px;font-weight:600;color:${isOff?"var(--ink-4)":"var(--blue)"};`;
    toggleLabel.textContent = isOff ? "Off" : "On";
    toggleWrap.appendChild(toggleInput);
    toggleWrap.appendChild(toggleLabel);

    header.appendChild(nameWrap);
    header.appendChild(toggleWrap);
    row.appendChild(header);

    // Schedule controls — shown only when on
    const controls = document.createElement("div");
    controls.style.cssText = `display:${isOff?"none":"block"};margin-top:14px;border-top:1px solid var(--border);padding-top:14px;`;

    // Frequency + time row
    const freqRow = document.createElement("div");
    freqRow.style.cssText = "display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px;";

    const freqLabel = document.createElement("div");
    freqLabel.style.cssText = "font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-4);flex-shrink:0;";
    freqLabel.textContent = "Frequency";

    const freqSel = document.createElement("select");
    freqSel.dataset.schedNiche = niche;
    freqSel.dataset.schedField = "frequency";
    freqSel.style.cssText = "font-size:12px;border:1px solid var(--border);border-radius:6px;padding:5px 8px;font-family:inherit;";
    ["daily","weekly","biweekly","monthly"].forEach(f => {
      const opt = document.createElement("option");
      opt.value = f;
      opt.textContent = f.charAt(0).toUpperCase() + f.slice(1);
      if (f === freq && !isOff) opt.selected = true;
      freqSel.appendChild(opt);
    });

    const timeLabel = document.createElement("div");
    timeLabel.style.cssText = "font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-4);flex-shrink:0;margin-left:8px;";
    timeLabel.textContent = "Time";

    const timeInput = document.createElement("input");
    timeInput.type = "time";
    timeInput.value = time;
    timeInput.dataset.schedNiche = niche;
    timeInput.dataset.schedField = "timeOfDay";
    timeInput.style.cssText = "font-size:12px;border:1px solid var(--border);border-radius:6px;padding:5px 8px;font-family:inherit;";

    freqRow.appendChild(freqLabel);
    freqRow.appendChild(freqSel);
    freqRow.appendChild(timeLabel);
    freqRow.appendChild(timeInput);
    controls.appendChild(freqRow);

    // Day of week checkboxes
    const daysLabel = document.createElement("div");
    daysLabel.style.cssText = "font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-4);margin-bottom:8px;";
    daysLabel.textContent = "Days — choose which days to generate content";
    controls.appendChild(daysLabel);

    const daysRow = document.createElement("div");
    daysRow.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;";
    DAYS.forEach((day, idx) => {
      const dayLabel = document.createElement("label");
      const isChecked = savedDays.length ? savedDays.includes(idx) : [1,3,5].includes(idx); // default Mon/Wed/Fri
      dayLabel.style.cssText = `
        display:flex;align-items:center;gap:4px;padding:5px 10px;border-radius:20px;cursor:pointer;
        border:1px solid ${isChecked?"var(--blue,#1749c9)":"var(--border)"};
        background:${isChecked?"var(--blue-dim,#eef2fb)":"transparent"};
        font-size:12px;font-weight:${isChecked?"600":"400"};
        color:${isChecked?"var(--blue,#1749c9)":"var(--ink-3)"};
        transition:all .12s;user-select:none;
      `;
      const dayCb = document.createElement("input");
      dayCb.type = "checkbox";
      dayCb.checked = isChecked;
      dayCb.dataset.dayIdx = idx;
      dayCb.dataset.schedNiche = niche;
      dayCb.style.cssText = "width:13px;height:13px;accent-color:var(--blue,#1749c9);cursor:pointer;";
      dayCb.addEventListener("change", () => {
        dayLabel.style.borderColor  = dayCb.checked ? "var(--blue,#1749c9)" : "var(--border)";
        dayLabel.style.background   = dayCb.checked ? "var(--blue-dim,#eef2fb)" : "transparent";
        dayLabel.style.color        = dayCb.checked ? "var(--blue,#1749c9)" : "var(--ink-3)";
        dayLabel.style.fontWeight   = dayCb.checked ? "600" : "400";
      });
      dayLabel.appendChild(dayCb);
      dayLabel.appendChild(document.createTextNode(day));
      daysRow.appendChild(dayLabel);
    });
    controls.appendChild(daysRow);

    // Save button
    const saveBtn = document.createElement("button");
    saveBtn.className = "btn-primary";
    saveBtn.style.cssText = "font-size:12px;padding:7px 18px;";
    saveBtn.dataset.schedSave = niche;
    saveBtn.textContent = "Save Schedule";
    controls.appendChild(saveBtn);

    row.appendChild(controls);
    container.appendChild(row);

    // Toggle on/off
    toggleInput.addEventListener("change", () => {
      const on = toggleInput.checked;
      toggleLabel.textContent  = on ? "On" : "Off";
      toggleLabel.style.color  = on ? "var(--blue)" : "var(--ink-4)";
      controls.style.display   = on ? "block" : "none";
      nicheName.style.color    = on ? "var(--blue)" : "var(--ink-3)";
      row.style.borderColor    = on ? "var(--blue-border,rgba(23,73,201,0.25))" : "var(--border)";
      nextRun.textContent      = on ? "Not yet scheduled" : "Auto-generation off";
      if (!on) {
        // Save as off immediately
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Denver";
        authFetch(`${BACKEND_URL}/schedules`, {
          method:"POST",
          body:JSON.stringify({ niche, frequency:"weekly", timeOfDay:time, timezone:tz, active:false, dayOfWeek:JSON.stringify([]) })
        }).catch(()=>{});
      }
    });

    // Save button handler
    saveBtn.addEventListener("click", async () => {
      const freq2  = freqSel.value;
      const time2  = timeInput.value;
      const days   = [...daysRow.querySelectorAll("input[type=checkbox]")]
                       .filter(c => c.checked)
                       .map(c => parseInt(c.dataset.dayIdx));
      saveBtn.textContent = "Saving…"; saveBtn.disabled = true;
      try {
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Denver";
        await authFetch(`${BACKEND_URL}/schedules`, {
          method:"POST",
          body:JSON.stringify({ niche, frequency:freq2, timeOfDay:time2, timezone:tz, active:true, dayOfWeek:JSON.stringify(days) })
        });
        await loadSchedules(); renderScheduleUI();
      } catch(e) {
        saveBtn.textContent = "Save Schedule"; saveBtn.disabled = false;
      }
    });
  });
}

// ─────────────────────────────────────────────
// SECTION 23: IDENTITY SUMMARY + TRENDS DISPLAY
// ─────────────────────────────────────────────
function renderIdentitySummary() {
  const container = el("identity-summary-content"); if (!container) return;
  const saved     = getSaved();
  const primaries = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  if (!saved.agentName && !primaries.length) {
    container.innerHTML = '<span style="font-size:13px;color:var(--ink-3);">No identity set. <a href="#" onclick="navigateTo(\'setup-panel\');return false;" style="color:var(--gold);font-weight:600;">Go to Identity →</a></span>';
    return;
  }

  // Ensure ceSelectedNiche is initialised to first niche if not already set
  if (!ceSelectedNiche || !primaries.includes(ceSelectedNiche)) {
    ceSelectedNiche = primaries[0] || null;
  }

  let html = '<div style="margin-bottom:10px;">';
  // Name + market line
  if (saved.agentName || saved.market) {
    html += `<div style="font-size:13px;font-weight:700;color:var(--ink);margin-bottom:8px;">${saved.agentName||""}${saved.market ? `<span style="font-weight:400;color:var(--ink-3);"> · ${saved.market}</span>` : ""}</div>`;
  }

  // Selectable niche pills — one tap sets the active niche for generation + compliance
  if (primaries.length > 0) {
    html += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px;">';
    primaries.forEach(p => {
      const isActive = ceSelectedNiche === p;
      const safe = p.replace(/'/g, "\\'");
      if (isActive) {
        html += `<span onclick="ceSetNicheFromIdentity('${safe}')" style="display:inline-flex;align-items:center;padding:4px 12px;border-radius:var(--radius-pill);background:var(--gold);border:1.5px solid var(--gold);font-size:12px;font-weight:700;color:#fff;cursor:pointer;user-select:none;">${p}</span>`;
      } else {
        html += `<span onclick="ceSetNicheFromIdentity('${safe}')" style="display:inline-flex;align-items:center;padding:4px 12px;border-radius:var(--radius-pill);background:var(--gold-dim);border:1.5px solid var(--gold-border);font-size:12px;font-weight:600;color:var(--gold);cursor:pointer;user-select:none;opacity:0.7;">${p}</span>`;
      }
    });
    html += '</div>';
    if (primaries.length > 1) {
      html += `<div style="font-size:11px;color:var(--ink-3);margin-top:2px;">Tap a niche to select it for this post.</div>`;
    }
  }

  // Sub-niches for active niche — shown as selectable pills to further focus the post
  const subs = ceSelectedNiche
    ? (NICHE_DATA[ceSelectedNiche]||[]).filter(s => (saved.subNiches||[]).includes(s))
    : [];
  if (subs.length) {
    html += '<div style="margin-top:8px;">';
    html += '<div style="font-size:11px;color:var(--ink-3);margin-bottom:4px;">Focus on a sub-niche (optional):</div>';
    html += '<div style="display:flex;flex-wrap:wrap;gap:5px;">';
    subs.forEach(sub => {
      const isActiveSub = ceSelectedSubNiche === sub;
      const safeSub = sub.replace(/'/g, "\'");
      if (isActiveSub) {
        html += `<span onclick="ceSetSubNiche('${safeSub}')" style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:var(--radius-pill);background:var(--gold-dim);border:1.5px solid var(--gold);font-size:11px;font-weight:700;color:var(--gold);cursor:pointer;user-select:none;">${sub} ✓</span>`;
      } else {
        html += `<span onclick="ceSetSubNiche('${safeSub}')" style="display:inline-flex;align-items:center;padding:3px 10px;border-radius:var(--radius-pill);background:transparent;border:1.5px solid var(--border);font-size:11px;font-weight:500;color:var(--ink-3);cursor:pointer;user-select:none;">${sub}</span>`;
      }
    });
    html += '</div></div>';
  }

  html += '</div>';
  container.innerHTML = html;
}

// Called when an agent taps a niche pill in the identity summary block.
// Updates ceSelectedNiche and re-renders the summary to show the new active state.
// Also refreshes the situation dropdown if we're in guided mode.
let ceSelectedSubNiche = null;

function ceSetNicheFromIdentity(niche) {
  ceSelectedNiche = niche;
  ceSelectedSubNiche = null; // reset sub-niche when top-level niche changes
  renderIdentitySummary();
  // If in guided mode, update the situation dropdown and persona for the new niche
  if (_ceActiveMode === "guided") {
    populateSituationDropdown(niche);
    updatePersonaDropdown(niche);
  }
}

// Called when an agent taps a sub-niche pill — toggles selection
function ceSetSubNiche(sub) {
  ceSelectedSubNiche = (ceSelectedSubNiche === sub) ? null : sub;
  renderIdentitySummary();
}



// Identity toggle accordion
el("identity-toggle")?.addEventListener("click", () => {
  const content = el("identity-content"); const arrow = el("identity-arrow"); if (!content) return;
  const open = content.style.display !== "none";
  content.style.display = open ? "none" : "block";
  if (arrow) arrow.textContent = open ? "▸" : "▾";
});

// ─────────────────────────────────────────────
// SECTION 24: SITUATION DROPDOWN + PERSONA
// ─────────────────────────────────────────────
// ── Niche name mapping: frontend NICHE_CATEGORIES → backend NICHE_SITUATIONS keys ──
const NICHE_SITUATION_MAP = {
  // Transaction & Situation
  "Buyer representation":          "Residential Buying & Selling",
  "Seller representation":         "Residential Buying & Selling",
  "Probate sales":                  "Probate & Inherited Homes",
  "Probate / inherited homes":      "Probate & Inherited Homes",
  "Divorce sales":                  "Divorce & Separation",
  "Divorce-related sales":          "Divorce & Separation",
  "Foreclosure":                    "Short Sale & Foreclosure",
  "Pre-foreclosure":                "Pre-Foreclosure & Hardship",
  "REO / bank-owned":               "Short Sale & Foreclosure",
  "Bankruptcy":                     "Pre-Foreclosure & Hardship",
  "Estate sales":                   "Estate & Probate Sales",
  "1031 exchange clients":          "Investment Analysis",
  "1031 exchange":                  "Investment Analysis",
  "Off-market / pocket listings":   "Residential Buying & Selling",
  "Creative finance":               "Residential Buying & Selling",
  // Customer Type
  "First-time homebuyers":          "First-Time Homebuyers",
  "Move-up buyers":                 "Move-Up Buyers",
  "Downsizers":                     "Empty Nesters & Downsizing",
  "Luxury buyers & sellers":        "Luxury Real Estate",
  "Seniors / 55+":                  "Seniors & 55+ Communities",
  "Seniors & retirees":             "Seniors & 55+ Communities",
  "Military families":              "Veterans & Military",
  "Relocation clients":             "Relocation",
  "Second-home buyers":             "Second Homes & Vacation",
  "Vacation-home buyers":           "Second Homes & Vacation",
  "Work-from-home buyers":          "Residential Buying & Selling",
  "Pet-focused buyers":             "Residential Buying & Selling",
  "Families with special housing needs": "Families with Children",
  "Empty nesters":                  "Empty Nesters & Downsizing",
  "Young professionals":            "Young Professionals",
  "Divorcing couples":              "Divorce & Separation",
  "Adult children helping parents": "Care-Driven Transitions",
  "Foreign nationals & expats":     "Relocation",
  "High-net-worth / UHNW clients":  "Ultra-Luxury / UHNW",
  "Multigenerational families":     "Families with Children",
  "Remote workers":                 "Residential Buying & Selling",
  "Teachers & essential workers":   "Residential Buying & Selling",
  "LGBTQ+ friendly":                "Residential Buying & Selling",
  "Veterans & VA buyers":           "Veterans & Military",
  // Property Type
  "Single-family homes":            "Residential Buying & Selling",
  "Condos & townhomes":             "Condos & Townhomes",
  "Multi-family residential":       "Multi-Family (2-4 Units)",
  "Commercial retail":              "Retail & Mixed-Use",
  "Commercial office":              "Office Space",
  "Commercial industrial":          "Industrial & Warehouse",
  "Land & lots":                    "Land & Development",
  "Agricultural land":              "Ranch & Farm / Agricultural",
  "Farms & ranches":                "Ranch & Farm / Agricultural",
  "Vineyard properties":            "Ranch & Farm / Agricultural",
  "Waterfront properties":          "Recreational & Mountain",
  "Historic homes":                 "Residential Buying & Selling",
  "Eco-friendly / green homes":     "Residential Buying & Selling",
  "Smart homes":                    "Residential Buying & Selling",
  // Investment
  "Buy-and-hold":                   "Investment Analysis",
  "Fix & flip":                     "Fix & Flip",
  "BRRRR":                          "Long-Term Rentals (BRRRR)",
  "Small multifamily (2–4 units)":  "Multi-Family (2-4 Units)",
  "Apartment buildings (5+ units)": "Multi-Family (5+ Units)",
  "Cash flow focused":              "Investment Analysis",
  "Appreciation focused":           "Investment Analysis",
  "Investor clients":               "Investment Analysis",
  "Opportunity zones":              "Opportunity Zones",
  // Rental
  "Long-term rentals":              "Long-Term Rentals (BRRRR)",
  "Short-term rentals":             "Short-Term Rentals / Airbnb",
  "Vacation rentals":               "Short-Term Rentals / Airbnb",
  "Airbnb-style rentals":           "Short-Term Rentals / Airbnb",
  "Student rentals":                "Residential Leasing",
  "Section 8 / affordable housing": "Residential Leasing",
  "Rent-to-own":                    "Residential Leasing",
  "Landlord representation":        "Property Management",
  "Mid-term / corporate rentals":   "Mid-Term Rentals",
  "Property management":            "Property Management",
  // New Construction
  "Builder representation":         "New Construction",
  "Master-planned communities":     "New Construction",
  "New subdivisions":               "New Construction",
  "Gated new developments":         "New Construction",
  "HOA communities":                "New Construction",
  "Custom-home builds":             "New Construction",
  "Spec homes":                     "New Construction",
  "Build-to-rent communities":      "New Construction",
  // Specialty
  "Resort properties":              "Recreational & Mountain",
  "Timeshares":                     "Second Homes & Vacation",
  "Equine properties":              "Ranch & Farm / Agricultural",
  "Farm & ranch specialty":         "Ranch & Farm / Agricultural",
  "Mobile & manufactured homes":    "Residential Buying & Selling",
  "Green & sustainable housing":    "Residential Buying & Selling",
  "Smart-home specialty":           "Residential Buying & Selling",
  "Multi-generational homes":       "Families with Children",
  "Data centers":                   "Data Centers",
  "Medical office":                 "Medical & Dental",
  "Hospitality":                    "Hospitality",
  "Mixed-use commercial":           "Retail & Mixed-Use",
  // Distressed
  "Burned-out landlords":           "Pre-Foreclosure & Hardship",
  "Care-driven housing transitions":"Care-Driven Transitions",
  "Emergency relocation":           "Emergency Relocation",
  // Location
  "Specific neighborhoods":         "Residential Buying & Selling",
  "Suburbs & master-planned communities": "New Construction",
  "ZIP-code specialist":            "Residential Buying & Selling",
  "City / regional expert":         "Residential Buying & Selling",
  "Waterfront communities":         "Recreational & Mountain",
  "Mountain communities":           "Recreational & Mountain",
  "Urban high-rises":               "Condos & Townhomes",
  "Historic districts":             "Residential Buying & Selling",
  "Gated communities":              "Luxury Real Estate",
  "Resort & vacation markets":      "Second Homes & Vacation",
  "Rural & acreage markets":        "Ranch & Farm / Agricultural",
};

function mapNicheToBackend(niche) {
  if (!niche) return niche;
  // Exact match first
  if (NICHE_SITUATION_MAP[niche]) return NICHE_SITUATION_MAP[niche];
  // Case-insensitive fallback
  const lower = niche.toLowerCase();
  const key = Object.keys(NICHE_SITUATION_MAP).find(k => k.toLowerCase() === lower);
  return key ? NICHE_SITUATION_MAP[key] : niche;
}

async function populateSituationDropdown(niche) {
  const select = el("situation-select"); if (!select) return;
  const isMarketing = getViewContext() === "marketing";
  if (isMarketing) {
    select.innerHTML = '<option value="">Select a situation…</option>';
    SITUATIONS_B2B.forEach(s => { const o = document.createElement("option"); o.value = s; o.textContent = s; select.appendChild(o); });
    select.disabled = false;
    return;
  }
  select.innerHTML = '<option value="">Loading…</option>'; select.disabled = true;
  try {
    const saved        = getSaved();
    const allNiches    = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
    const targetNiches = niche ? [niche] : allNiches;
    let situations;
    if (targetNiches.length) {
      try {
        let url;
        if (targetNiches.length === 1) {
          url = `${BACKEND_URL}/content/situations?niche=${encodeURIComponent(mapNicheToBackend(targetNiches[0]))}`;
        } else {
          const nicheParam = targetNiches.map(n => encodeURIComponent(mapNicheToBackend(n))).join(",");
          url = `${BACKEND_URL}/content/situations/multi?niches=${nicheParam}`;
        }
        const res  = await authFetch(url);
        const data = await res.json();
        // Use backend if it returns niche-specific results; otherwise local map
        situations = (data.situations && data.situations.length) ? data.situations : getNicheSituations(targetNiches);
      } catch(e) {
        situations = getNicheSituations(targetNiches);
      }
    } else {
      situations = getNicheSituations([]);
    }
    select.innerHTML = '<option value="">Select a situation…</option>';
    situations.forEach(s => { const o = document.createElement("option"); o.value = s; o.textContent = s; select.appendChild(o); });
  } catch(e) {
    const saved     = getSaved();
    const allNiches = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
    const fallback  = getNicheSituations(niche ? [niche] : allNiches);
    select.innerHTML = '<option value="">Select a situation…</option>';
    fallback.forEach(s => { const o = document.createElement("option"); o.value = s; o.textContent = s; select.appendChild(o); });
  } finally { select.disabled = false; }
}

function trackPersonaUsed(val) {
  if (!val) return;
  const recent = JSON.parse(localStorage.getItem("hb_recent_personas") || "[]");
  localStorage.setItem("hb_recent_personas", JSON.stringify([val, ...recent.filter(v=>v!==val)].slice(0,5)));
}

function updatePersonaDropdown(niche) {
  const select = el("persona-select"); if (!select) return;
  const isMarketing = getViewContext() === "marketing";
  if (isMarketing) {
    select.innerHTML = '<option value="">No specific audience</option>';
    PERSONAS_B2B.forEach(v => { const o = document.createElement("option"); o.value = v; o.textContent = v; select.appendChild(o); });
    return;
  }
  // Build niche-aware list from all selected primary niches
  const saved    = getSaved();
  const niches   = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  const recent   = JSON.parse(localStorage.getItem("hb_recent_personas") || "[]");
  // Collect personas for all selected niches, deduplicated, in order
  const matched  = [...new Set(niches.flatMap(n => NICHE_PERSONAS[mapNicheToBackend(n)] || NICHE_PERSONAS[n] || []))];
  const opts     = matched.length ? matched : PERSONAS_GENERAL;
  // Put recently used at top if they match
  const recentMatched = recent.filter(r => opts.includes(r));
  const final    = [...new Set([...recentMatched, ...opts])];
  select.innerHTML = '<option value="">Who this is for (optional)</option>';
  final.forEach(v => { const o = document.createElement("option"); o.value = v; o.textContent = v; select.appendChild(o); });
}

// ─────────────────────────────────────────────
// SECTION 25: GENERATE CONTENT
// ─────────────────────────────────────────────
el("generate-content-btn")?.addEventListener("click", async () => {
  const saved     = getSaved();
  const primaries = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  const situation = el("situation-select")?.value || "";
  trackPersonaUsed(el("persona-select")?.value || "");

  if (!primaries.length) { showMsg("generate-error","⚠ Please complete Setup first — select at least one primary niche and click Save Setup.",true); return; }
  if (!situation)         { showMsg("generate-error","⚠ Please select a situation before generating.",true); return; }
  hideMsg("generate-error");

  const focusNiche  = activeNicheForGenerate || primaries[0];
  const subByCategory = {};
  primaries.forEach(p => { const subs = (NICHE_DATA[p]||[]).filter(s=>(saved.subNiches||[]).includes(s)); if (subs.length) subByCategory[p] = subs; });
  const hbUser = JSON.parse(localStorage.getItem("hb_user") || "null");

  const isMarketingCtx = getViewContext() === "marketing";
  const payload = {
    identity:    { primaryCategories:[focusNiche], subNichesByCategory:subByCategory, trendPreferences:saved.trends||[] },
    agentProfile:{ agentName:saved.agentName||hbUser?.agent_name||"", businessName:saved.businessName||"", brokerage:saved.brokerage||hbUser?.brokerage||"", market:getMarketContext(), brandVoice:saved.brandVoice||"", shortBio:saved.shortBio||"", audienceDescription:saved.audienceDescription||"", wordsAvoid:saved.wordsAvoid||"", wordsPrefer:saved.wordsPrefer||"", mlsNames:JSON.parse(localStorage.getItem("hb_mls")||"[]"), serviceAreas:getServiceAreas(), designations:getDesignations(), languagePref:getLanguagePref(), state:saved.state||"", ctaMethods:getCtaMethods(), ctaType:(getCtaMethods()[0]||{}).type||"", ctaUrl:(getCtaMethods()[0]||{}).url||"", ctaLabel:(getCtaMethods()[0]||{}).label||"", mlsData:el("mls-data-input")?.value.trim()||"", originStory:saved.originStory||"", unfairAdvantage:saved.unfairAdvantage||"", signaturePerspective:saved.signaturePerspective||"", notForClient:saved.notForClient||"" },
    situation, persona:el("persona-select")?.value||null, tone:el("tone-select")?.value||null, length:el("length-select")?.value||null,
    selectedTrends:saved.trends||[], timestamp:new Date().toISOString(),
    content_mode: isMarketingCtx ? "b2b" : "agent",
  };
  // Recruiting CTA
  payload.agentProfile.recruitingEnabled = saved.recruitingEnabled || false;
  payload.agentProfile.recruitingCta     = saved.recruitingCta     || "";
  // Sub-niche focus — if agent selected a sub-niche, inject it into the identity
  if (ceSelectedSubNiche && payload.identity.primaryCategories[0]) {
    const topNiche = payload.identity.primaryCategories[0];
    payload.identity.subNichesByCategory[topNiche] = [ceSelectedSubNiche];
  }
  // Store payload so review modal can regenerate with same settings
  window._lastGeneratePayload = { payload, focusNiche, isDemo: localStorage.getItem("hb_demo_mode") === "true" };

  const btn = el("generate-content-btn"); const indicator = el("generating-indicator");
  btn.disabled = true; btn.textContent = "Generating…";
  if (indicator) indicator.style.display = "block";
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";

  try {
    const res = await authFetch(`${BACKEND_URL}/content/generate-content`, { method:"POST", body:JSON.stringify(payload) });
    if (res.status === 429) {
      const errData = await res.json();
      const detail  = errData.detail || {};
      showMsg("generate-error", `⚠ ${detail.message || "Monthly limit reached."} Resets ${detail.resets_on || "next month"}.`, true);
      return;
    }
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    const contentPayload = { headline:data.headline||"", thumbnailIdea:data.thumbnailIdea||"", hashtags:data.hashtags||"", post:data.post||"", cta:data.cta||"", script:data.script||"" };
    if (isDemo) {
      const demoItem = { id:"demo-"+Date.now(), niche:focusNiche, content:contentPayload, compliance:data.compliance||null, status:"pending", created_at:new Date().toISOString(), is_demo:true };
      if (!window._demoLibrary) window._demoLibrary = [];
      window._demoLibrary.unshift(demoItem);
      window._demoLibrary.sort((a,b) => new Date(b.created_at||b.savedAt||0) - new Date(a.created_at||a.savedAt||0));
      navigateTo("library-panel"); openReviewModal(demoItem);
    } else {
      const libraryItem = await apiSaveLibraryItem(focusNiche, contentPayload, data.compliance||null);
      navigateTo("library-panel"); openReviewModal(libraryItem);
    }
  } catch(err) {
    if (err.message !== "Session expired") showMsg("generate-error","⚠ Content generation failed. Please check your connection and try again.",true);
  } finally {
    btn.disabled = false; btn.textContent = "✦ Generate Content";
    if (indicator) indicator.style.display = "none";
  }
});

// ─────────────────────────────────────────────
// SECTION 25A: HOME DASHBOARD
// ─────────────────────────────────────────────

// Safe home-panel openers — look up items from cache by ID
// Avoids fragile inline JSON in onclick attributes
async function homeOpenReview(btn) {
  const itemId = btn.dataset.reviewId;
  const lib = await fetchLibrary();
  const item = lib.find(x => String(x.id) === String(itemId));
  if (item) { _reviewModalOrigin = "home"; openReviewModal(item); }
}
async function homeOpenEdit(btn) {
  const itemId = btn.dataset.editId;
  const lib = await fetchLibrary();
  const item = lib.find(x => String(x.id) === String(itemId));
  if (item) { loadIntoWorkspace(item); navigateTo("workspace-panel"); }
}

// ─────────────────────────────────────────────
// JORDAN HOME BRIEFING
// Jordan's daily message on the Home screen.
// API-generated using character brief — NOT cached.
// Home is daily and always reflects current state.
// Different from Identity Jordan (standing record).
// Data: pending approvals, signals, schedules, published count.
// ─────────────────────────────────────────────

function _jordanHomeFallbackMessage(data) {
  const { pending, signals, schedules, published } = data;
  if (pending >= 3) {
    return `Your Auditor cleared ${pending} posts while you were away. They are ready for your review below.`;
  }
  if (pending && signals) {
    return `Your Auditor cleared ${pending} post${pending > 1 ? "s" : ""} and Your Analyst found a story worth writing about. Both are waiting below.`;
  }
  if (pending) {
    return `Your Auditor cleared ${pending} post${pending > 1 ? "s" : ""} while you were away. Ready when you are.`;
  }
  if (signals) {
    return `Your Analyst found something in your market worth writing about. Nothing is waiting for your approval right now.`;
  }
  if (schedules) {
    return `Your Scheduler has everything on track. Nothing needs your attention right now.`;
  }
  if (published >= 5) {
    return `Your team has been working hard. Everything is in good shape.`;
  }
  return `Your whole team is standing by. Create a post or set a schedule and they will get to work.`;
}

async function _jordanHomeGenerateMessage(data) {
  const { pending, signals, schedules, published } = data;
  const name  = jordanName();
  const brief = jordanBrief();

  // Message generation routes through backend — API key never exposed client-side.
  // System prompt and user prompt are built server-side in POST /jordan/message.
  try {
    const res = await authFetch(`${BACKEND_URL}/jordan/message`, {
      method: "POST",
      body: JSON.stringify({
        type:         "home",
        data:         { pending, signals, schedules, published },
        jordan_name:  name,
        jordan_brief: brief,
      }),
    });

    if (!res.ok) return _jordanHomeFallbackMessage(data);
    const result = await res.json();
    const message = result.message || "";
    return message || _jordanHomeFallbackMessage(data);
  } catch(e) {
    return _jordanHomeFallbackMessage(data);
  }
}

// ── Signal card builder — single source of truth for signal card HTML ──────
// Both renderHomeDashboard and _refreshSignalZoneOnly use this.
function _buildSignalCard(sig) {
  const areaEsc     = (sig.area || '').replace(/'/g,"\\'").replace(/"/g,'\\"');
  const headlineEsc  = (sig.headline || '').replace(/'/g,"\\'").replace(/"/g,'\\"').replace(/\n/g,' ');
  const summaryEsc   = (sig.summary  || '').replace(/'/g,"\\'").replace(/"/g,'\\"').replace(/\n/g,' ');
  const sigType      = (sig.signal_type || '');
  const _typeLabelMap = {
    'rss:market|news':   'Market News',
    'rss:market':        'Market News',
    'rss:news':          'Industry News',
    'rss:local':         'Local News',
    'local:market':      'Local · Market',
    'local:development': 'Local · Development',
    'local:news':        'Local · News',
    'metro:market':      'Metro · Market',
    'metro:news':        'Metro · News',
    'national:market':   'National · Market',
    'national:news':     'National · News',
  };
  const typeLabel = _typeLabelMap[sigType] ||
    (sig.signal_type || 'Local Intel').replace(/^(local|metro|national):/i, '$1 · ').replace(/[_|]/g,' ').replace(/rss/gi,'').trim() ||
    'Local Intel';
  const dateStr    = sig.published_date
    ? (() => { try { return new Date(sig.published_date + 'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); } catch(e){ return ''; } })()
    : '';
  const dateLine   = dateStr ? `<div class="home-signal-date">${dateStr}</div>` : '';
  const sourceLink = (sig.source_url && sig.source_url.trim())
    ? `<a class="home-signal-source" href="${sig.source_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">View source ↗</a>`
    : '';
  return `
    <div class="home-signal-card" onclick="homeLoadIntel('${areaEsc}', ${sig.id}, '${headlineEsc}', '${summaryEsc}', '${sigType}')">
      <div class="home-signal-mate-byline">🔍 Your Analyst found this · ${sig.area || ''}</div>
      <div class="home-signal-type">${typeLabel}</div>
      ${dateLine}
      <div class="home-signal-headline">${sig.headline || ''}</div>
      <div class="home-signal-summary">${sig.summary || ''}</div>
      ${sourceLink}
      <div class="home-signal-cta">Get Your Writer on this →</div>
    </div>`;
}

// Refresh signal zone only — used by 30-min timer, no full dashboard re-render
async function _refreshSignalZoneOnly() {
  if (_signalGenerating) return; // guard: don't wipe completion message
  const signalZone = el('home-signal-zone');
  if (!signalZone) return;
  const isDemo = localStorage.getItem('hb_demo_mode') === 'true';
  if (isDemo) return; // demo signals don't change
  try {
    const res     = await authFetch(`${BACKEND_URL}/signals/latest`);
    if (!res.ok) return;
    const data    = await res.json();
    const signals = data.signals || [];
    if (!signals.length) return; // keep existing display if nothing new
    signalZone.innerHTML = _buildSignalCard(signals[0]);
    if (signals.length > 1) {
      const more = document.createElement('div');
      more.style.cssText = 'margin-top:12px;';
      const orLabel = document.createElement('div');
      orLabel.style.cssText = 'font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-4);margin-bottom:8px;';
      orLabel.textContent = '— or try one of these';
      more.appendChild(orLabel);
      const chipWrap = document.createElement('div');
      chipWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;';
      signals.slice(1).forEach(s => {
        const chip = document.createElement('div');
        chip.className = 'chip';
        chip.style.cssText = 'cursor:pointer;font-size:12px;';
        chip.textContent = s.area + ': ' + s.headline.slice(0, 50) + (s.headline.length > 50 ? '…' : '');
        chip.onclick = () => homeLoadIntel(s.area, s.id);
        chipWrap.appendChild(chip);
      });
      more.appendChild(chipWrap);
      signalZone.appendChild(more);
    }
  } catch(e) { /* silent — keep existing display */ }
}

async function renderHomeDashboard() {
  // Score widget lives in Identity panel — not called here

  // ── Greeting + Jordan label ──────────────────────────────────────────────
  const greetingEl = el("home-greeting");
  const jordanLabelEl = el("home-jordan-label");
  if (greetingEl) {
    const hour = new Date().getHours();
    const user = JSON.parse(localStorage.getItem("hb_user") || "null");
    const firstName = (user?.agent_name || "").split(" ")[0] || "";
    const timeWord = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
    const timePart = hour < 12 ? "Morning" : hour < 17 ? "Afternoon" : "Evening";
    greetingEl.textContent = firstName ? `${timeWord}, ${firstName}.` : `${timeWord}.`;
    if (jordanLabelEl) jordanLabelEl.textContent = jordanName() + "\u2019s " + timePart + " Brief";
  }

  // Clear Jordan brief until data loads
  const jordanBriefEl = el("home-jordan-brief");
  if (jordanBriefEl) jordanBriefEl.textContent = "";

  const headlineEl = el("home-headline-moment");

  // Set all zones to loading state
  const signalZone      = el("home-signal-zone");
  const writerZone      = el("home-writer-zone");
  const pendingZone     = el("home-pending-zone");
  const itsYourTurnInit = el("home-its-your-turn-zone");
  const schedulerZone   = el("home-scheduler-zone");
  const recentZone      = el("home-recent-zone");
  const promptedZone    = el("home-prompted-zone");

  if (signalZone && !_signalGenerating) signalZone.innerHTML    = '<div style="font-size:13px;color:var(--ink-3);">Your Analyst is checking your market…</div>';
  if (writerZone)      writerZone.innerHTML      = '<div style="font-size:13px;color:var(--ink-3);">Loading…</div>';
  if (pendingZone)     pendingZone.innerHTML     = '<div style="font-size:13px;color:var(--ink-3);">Loading…</div>';
  if (itsYourTurnInit) itsYourTurnInit.innerHTML = '<div style="font-size:13px;color:var(--ink-3);">Loading…</div>';
  if (schedulerZone)   schedulerZone.innerHTML   = '<div style="font-size:13px;color:var(--ink-3);">Loading…</div>';
  if (recentZone)      recentZone.innerHTML      = '<div style="font-size:13px;color:var(--ink-3);">Loading…</div>';
  if (promptedZone)    promptedZone.innerHTML    = '<div style="font-size:13px;color:var(--ink-3);">Loading…</div>';

  // Fetch all data in parallel
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  let signals = [], lib = [], scheds = [];

  try {
    const [sigRes, libData, schedRes] = await Promise.allSettled([
      isDemo
        ? Promise.resolve({ signals: window._demoSignals || [] })
        : authFetch(`${BACKEND_URL}/signals/latest`).then(r => r.json()),
      fetchLibrary(),
      authFetch(`${BACKEND_URL}/schedules`).then(r => r.json()),
    ]);
    signals = sigRes.status === "fulfilled"   ? (sigRes.value.signals || [])                           : [];
    lib     = libData.status === "fulfilled"  ? (libData.value || [])                                  : [];
    scheds  = schedRes.status === "fulfilled" ? (schedRes.value.schedules || []).filter(s => s.active) : [];
  } catch(e) { /* continue with empty data */ }

  // Split library by source
  const autoLib     = lib.filter(x => x.source !== "manual" && x.source !== "studio");
  const promptedLib = lib.filter(x => x.source === "manual" || x.source === "studio");

  const autoPending     = autoLib.filter(x => x.status === "pending");
  const promptedPending = promptedLib.filter(x => x.status === "pending");
  const published       = lib.filter(x => x.status === "approved" || x.status === "published");
  const allPending      = lib.filter(x => x.status === "pending");

  // ── Jordan Home briefing — API-generated, never cached ───────────────────
  // Fallback renders immediately so Jordan is never blank.
  // API message replaces it once the call resolves.
  // home-jordan-brief is cleared — Jordan speaks once, in the headline slot.
  const homeJordanData = {
    pending:   allPending.length,
    signals:   signals.length,
    schedules: scheds.length,
    published: published.length,
  };

  if (headlineEl) {
    headlineEl.textContent = _jordanHomeFallbackMessage(homeJordanData);
  }
  if (jordanBriefEl) jordanBriefEl.textContent = "";

  // Fire API call after zones begin rendering — non-blocking
  if (!isDemo && headlineEl) {
    _jordanHomeGenerateMessage(homeJordanData).then(msg => {
      if (msg && headlineEl) headlineEl.textContent = msg;
    }).catch(() => { /* fallback already shown */ });
  }

  // ── Down arrow — quiet visual cue, not a navigation button ─────────────
  // Replaced context-aware action button — header is orientation, not action.

  // ── YOUR ANALYST zone ─────────────────────────────────────────────────────
  if (signalZone && !_signalGenerating) {
    if (signals.length) {
      signalZone.innerHTML = _buildSignalCard(signals[0]);
      if (signals.length > 1) {
        const more = document.createElement("div");
        more.style.cssText = "margin-top:12px;";
        const orLabel = document.createElement("div");
        orLabel.style.cssText = "font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-4);margin-bottom:8px;";
        orLabel.textContent = "— or try one of these";
        more.appendChild(orLabel);
        const chipWrap = document.createElement("div");
        chipWrap.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;";
        signals.slice(1).forEach(s => {
          const chip = document.createElement("div");
          chip.className = "chip";
          chip.style.cssText = "cursor:pointer;font-size:12px;";
          chip.textContent = s.area + ": " + s.headline.slice(0, 50) + (s.headline.length > 50 ? "…" : "");
          chip.onclick = () => homeLoadIntel(s.area, s.id);
          chipWrap.appendChild(chip);
        });
        more.appendChild(chipWrap);
        signalZone.appendChild(more);
      }
    } else {
      signalZone.innerHTML = '<div style="font-size:13px;color:var(--ink-3);">Watching your market. Nothing new to report yet today.</div>';
    }
  }

  // ── YOUR WRITER zone ──────────────────────────────────────────────────────
  if (writerZone) {
    const recentAutoTotal = autoLib.slice(0, 7).length;
    const thisWeek = autoLib.filter(x => {
      const d = x.created_at || x.savedAt || "";
      if (!d) return false;
      const created = new Date(d);
      const now = new Date();
      const diff = (now - created) / (1000 * 60 * 60 * 24);
      return diff <= 7;
    }).length;
    if (thisWeek > 0) {
      writerZone.innerHTML = `<div style="font-size:13px;color:var(--ink-3);">Drafted <strong style="color:var(--ink);">${thisWeek} post${thisWeek > 1 ? "s" : ""}</strong> for you in the last 7 days.</div>`;
    } else if (recentAutoTotal > 0) {
      writerZone.innerHTML = `<div style="font-size:13px;color:var(--ink-3);">Nothing drafted this week. <a href="#" onclick="navigateTo('content-engine-panel');return false;" style="color:var(--gold);font-weight:600;">Brief Your Writer in Studio →</a></div>`;
    } else {
      writerZone.innerHTML = `<div style="font-size:13px;color:var(--ink-3);">Standing by. Your Scheduler will brief Your Writer when it's time. <a href="#" onclick="navigateTo('content-engine-panel');return false;" style="color:var(--gold);font-weight:600;">Or go to Studio →</a></div>`;
    }
  }

  // ── YOUR AUDITOR zone — status report only ───────────────────────────────
  if (pendingZone) {
    if (autoPending.length) {
      pendingZone.innerHTML = `<div style="font-size:13px;color:var(--ink-3);">Cleared <strong style="color:var(--ink);">${autoPending.length} post${autoPending.length > 1 ? "s" : ""}</strong> for your review. Your turn below.</div>`;
    } else {
      pendingZone.innerHTML = '<div style="font-size:13px;color:var(--ink-3);">Nothing waiting for your approval right now.</div>';
    }
  }

  // ── IT'S YOUR TURN zone — approval cards live here ────────────────────────
  const itsYourTurnZone = el("home-its-your-turn-zone");
  if (itsYourTurnZone) {
    const pendingSlice = autoPending.slice(0, 3);
    if (pendingSlice.length) {
      itsYourTurnZone.innerHTML = "";
      pendingSlice.forEach(item => {
        const cd       = item.content || {};
        const headline = cd.headline || "";
        const isBroken = !headline ||
          headline.toLowerCase().includes("error") ||
          headline.toLowerCase().includes("please try again") ||
          headline.toLowerCase().includes("generation failed") ||
          headline.toLowerCase().includes("could not") ||
          headline.length < 8;
        const card = document.createElement("div");
        card.className = "home-pending-card";
        if (isBroken) {
          card.style.cssText = "border-color:var(--amber);background:#fffbeb;";
          card.innerHTML = `
            <div class="home-pending-niche">${item.niche || ""}</div>
            <div style="font-size:13px;color:var(--amber);font-weight:600;margin-bottom:6px;">⚠ Generation failed for this post</div>
            <div style="font-size:12px;color:var(--ink-3);margin-bottom:10px;line-height:1.5;">Something went wrong when this was auto-generated. Tap below to try again.</div>
            <div class="home-pending-actions">
              <button class="btn-primary" style="padding:8px 18px;font-size:13px;background:var(--amber);" onclick="homePendingRegenerate(${item.id}, '${(item.niche||'').replace(/'/g,"\\'")}', this)">↺ Regenerate</button>
              <button class="btn-secondary" style="padding:8px 14px;font-size:13px;color:var(--red);" onclick="homePendingDelete(${item.id}, this)">Delete</button>
            </div>`;
        } else {
          card.innerHTML = `
            <div class="home-pending-niche">${item.niche || ""}</div>
            <div class="home-pending-headline">${headline}</div>
            <div class="home-pending-actions">
              <button class="btn-primary" style="padding:8px 18px;font-size:13px;" data-review-id="${item.id}" onclick="homeOpenReview(this)">Review &amp; Approve</button>
              <button class="btn-secondary" style="padding:8px 14px;font-size:13px;" data-edit-id="${item.id}" onclick="homeOpenEdit(this)">Edit</button>
              <button class="btn-secondary" style="padding:8px 14px;font-size:13px;color:var(--red);" onclick="homePendingDelete(${item.id}, this)">Dismiss</button>
            </div>`;
        }
        itsYourTurnZone.appendChild(card);
      });
      if (autoPending.length > 3) {
        const more = document.createElement("a");
        more.href = "#";
        more.style.cssText = "font-size:13px;color:var(--gold);font-weight:600;display:block;margin-top:8px;";
        more.textContent = `+ ${autoPending.length - 3} more waiting →`;
        more.onclick = (e) => { e.preventDefault(); navigateTo("library-panel"); };
        itsYourTurnZone.appendChild(more);
      }
    } else {
      itsYourTurnZone.innerHTML = `
        <div class="home-team-card" style="border-left-color:var(--border);background:var(--bg-sunken,#F0EEE9);">
          <div style="font-size:13px;color:var(--ink-3);">You're all caught up — nothing to review right now. Your CIR™ record is created the moment you approve a post.</div>
        </div>`;
    }
  }

  // ── YOUR SCHEDULER zone ───────────────────────────────────────────────────
  if (schedulerZone) {
    if (scheds.length) {
      const next    = scheds.sort((a,b) => (a.nextRun||"").localeCompare(b.nextRun||""))[0];
      const nextFmt = next.nextRun
        ? new Date(next.nextRun + "Z").toLocaleString("en-US",{weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})
        : "soon";
      schedulerZone.innerHTML = `<div style="font-size:13px;color:var(--ink-3);">Your next post goes out <strong style="color:var(--ink);">${nextFmt}</strong>.</div>`;
    } else {
      schedulerZone.innerHTML = `<div style="font-size:13px;color:var(--ink-3);">No schedule set yet. <a href="#" onclick="navigateTo('setup-panel');return false;" style="color:var(--gold);font-weight:600;">Set one in Identity and your team runs automatically →</a></div>`;
    }
  }

  // ── YOUR PUBLISHER zone ───────────────────────────────────────────────────
  if (recentZone) {
    const recent = published.slice(0, 3);
    if (recent.length) {
      recentZone.innerHTML = "";
      recent.forEach(item => {
        const cd  = item.content || {};
        const div = document.createElement("div");
        div.className = "home-recent-card";
        const cirBadge = item.cir_id
          ? `<span style="font-size:10px;font-weight:700;color:var(--gold);background:rgba(200,150,60,0.1);padding:2px 8px;border-radius:10px;letter-spacing:0.05em;">CIR™</span>`
          : "";
        div.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <div style="font-size:12px;color:var(--ink-3);">${item.niche||""} · ${(item.approvedAt||item.savedAt||"").slice(0,10)}</div>
            ${cirBadge}
          </div>
          <div style="font-size:13px;font-weight:600;color:var(--ink);margin-top:4px;line-height:1.4;">${cd.headline||"Post"}</div>`;
        div.style.cursor = "pointer";
        div.onclick = () => { loadIntoWorkspace(item); navigateTo("workspace-panel"); };
        recentZone.appendChild(div);
      });
      const viewAll = document.createElement("a");
      viewAll.href="#";
      viewAll.style.cssText = "font-size:13px;color:var(--gold);font-weight:600;display:block;margin-top:8px;";
      viewAll.textContent = "View Records →";
      viewAll.onclick = (e) => { e.preventDefault(); navigateTo("library-panel"); };
      recentZone.appendChild(viewAll);
    } else {
      recentZone.innerHTML = '<div style="font-size:13px;color:var(--ink-3);">Nothing sent yet. Your first published post will appear here.</div>';
    }
  }

  // ── YOUR REQUESTS zone ────────────────────────────────────────────────────
  if (promptedZone) {
    const promptedSlice = promptedPending.slice(0, 3);
    if (promptedSlice.length) {
      promptedZone.innerHTML = "";
      promptedSlice.forEach(item => {
        const cd       = item.content || {};
        const headline = cd.headline || "";
        const card = document.createElement("div");
        card.className = "home-pending-card";
        card.innerHTML = `
          <div class="home-pending-niche">${item.niche || ""} · <span style="color:var(--gold);font-weight:600;">Studio</span></div>
          <div class="home-pending-headline">${headline}</div>
          <div class="home-pending-actions">
            <button class="btn-primary" style="padding:8px 18px;font-size:13px;" data-review-id="${item.id}" onclick="homeOpenReview(this)">Review &amp; Approve</button>
            <button class="btn-secondary" style="padding:8px 14px;font-size:13px;" data-edit-id="${item.id}" onclick="homeOpenEdit(this)">Edit</button>
            <button class="btn-secondary" style="padding:8px 14px;font-size:13px;color:var(--red);" onclick="homePendingDelete(${item.id}, this)">Dismiss</button>
          </div>`;
        promptedZone.appendChild(card);
      });
      if (promptedPending.length > 3) {
        const more = document.createElement("a");
        more.href = "#";
        more.style.cssText = "font-size:13px;color:var(--gold);font-weight:600;display:block;margin-top:8px;";
        more.textContent = `+ ${promptedPending.length - 3} more waiting →`;
        more.onclick = (e) => { e.preventDefault(); navigateTo("library-panel"); };
        promptedZone.appendChild(more);
      }
    } else {
      promptedZone.innerHTML = `<div style="font-size:13px;color:var(--ink-3);">You haven't asked for anything lately. <a href="#" onclick="navigateTo('content-engine-panel');return false;" style="color:var(--gold);font-weight:600;">Head to Studio to brief your team →</a></div>`;
    }
  }
}

async function homePendingRegenerate(itemId, niche, btn) {
  // Delete the broken item and generate a fresh one for the same niche
  const card = btn.closest(".home-pending-card");
  btn.disabled = true; btn.textContent = "Regenerating…";
  try {
    // Delete the broken item first
    await apiDeleteLibraryItem(itemId);
    // Generate a fresh post for this niche
    const saved  = getSaved();
    const hbUser = JSON.parse(localStorage.getItem("hb_user") || "null");
    const situations = getNicheSituations([niche]);
    const situation  = situations[Math.floor(Math.random() * situations.length)] || "Market update and current conditions";
    const payload = {
      identity:    { primaryCategories:[niche], subNichesByCategory:{}, trendPreferences:[] },
      agentProfile: ceAgentProfilePayload(),
      situation,
      persona:null, tone:null, length:"medium",
      content_mode: "agent",
    };
    const res = await authFetch(`${BACKEND_URL}/content/generate-content`, { method:"POST", body:JSON.stringify(payload) });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    const contentPayload = { headline:data.headline||"", thumbnailIdea:data.thumbnailIdea||"", hashtags:data.hashtags||"", post:data.post||"", cta:data.cta||"", script:data.script||"" };
    await apiSaveLibraryItem(niche, contentPayload, data.compliance||null);
    // Refresh the home panel pending zone
    if (card) card.innerHTML = `<div style="font-size:13px;color:var(--green);font-weight:600;">✓ New post generated — refresh to review.</div>`;
    // Re-render after short delay
    setTimeout(() => renderHomeDashboard(), 1200);
  } catch(e) {
    btn.disabled = false; btn.textContent = "↺ Regenerate";
    if (card) {
      const errDiv = document.createElement("div");
      errDiv.style.cssText = "font-size:12px;color:var(--red);margin-top:6px;";
      errDiv.textContent = "Regeneration failed — please check your connection and try again.";
      card.appendChild(errDiv);
    }
  }
}

async function homePendingDelete(itemId, btn) {
  const card = btn.closest(".home-pending-card");
  btn.disabled = true; btn.textContent = "Deleting…";
  try {
    await apiDeleteLibraryItem(itemId);
    if (card) card.style.opacity = "0";
    setTimeout(() => renderHomeDashboard(), 400);
  } catch(e) {
    btn.disabled = false; btn.textContent = "Delete";
  }
}

let _signalGenerating = false; // guard: prevent renderHomeDashboard from wiping completion message
let _reviewModalOrigin = null; // tracks which panel opened the review modal — 'home' | null

// ── Niche picker state — set when modal opens, read when confirmed ──
let _nichePickerPending = null; // { area, signalId, headline, summary, sigType }
let _nichePickerSelected = null; // niche string

function _homeShowNichePicker(area, signalId, headline, summary, sigType) {
  const saved    = getSaved();
  const niches   = Array.isArray(saved.primaryNiches) && saved.primaryNiches.length
    ? saved.primaryNiches
    : ["Residential Buying & Selling"];

  // Default to first niche — agent can change
  _nichePickerSelected = niches[0];
  _nichePickerPending  = { area, signalId, headline, summary, sigType };

  // Populate headline
  const headEl = el("niche-picker-headline");
  if (headEl) headEl.textContent = headline || "Signal from Your Analyst";

  // Build niche chips
  const chipsEl = el("niche-picker-chips");
  if (chipsEl) {
    chipsEl.innerHTML = niches.map(n => {
      const selected = n === _nichePickerSelected;
      return `<div class="chip${selected ? " selected" : ""}" style="cursor:pointer;font-size:12px;font-weight:${selected ? "700" : "500"};" onclick="_nichePickerSelect(this, '${n.replace(/'/g, "\'")}')">${n}</div>`;
    }).join("");
  }

  // Show modal
  const backdrop = el("niche-picker-backdrop");
  if (backdrop) backdrop.style.display = "flex";
}

function _nichePickerSelect(chip, niche) {
  _nichePickerSelected = niche;
  const chipsEl = el("niche-picker-chips");
  if (chipsEl) {
    chipsEl.querySelectorAll(".chip").forEach(c => {
      const isThis = c === chip;
      c.classList.toggle("selected", isThis);
      c.style.fontWeight = isThis ? "700" : "500";
    });
  }
}

function closeNichePicker() {
  const backdrop = el("niche-picker-backdrop");
  if (backdrop) backdrop.style.display = "none";
  _nichePickerPending  = null;
  _nichePickerSelected = null;
}

function confirmNichePicker() {
  const backdrop = el("niche-picker-backdrop");
  if (backdrop) backdrop.style.display = "none";
  if (!_nichePickerPending) return;
  const { area, signalId, headline, summary, sigType } = _nichePickerPending;
  const niche = _nichePickerSelected || (getSaved().primaryNiches||[])[0] || "Residential Buying & Selling";
  _nichePickerPending  = null;
  _nichePickerSelected = null;
  _homeRunIntel(area, signalId, headline, summary, sigType, niche);
}

async function homeLoadIntel(area, signalId, headline, summary, sigType) {
  // Show niche picker first — agent confirms who this post is written for
  // before generation fires. Defaults to primaryNiches[0].
  _homeShowNichePicker(area, signalId, headline, summary, sigType);
}

async function _homeRunIntel(area, signalId, headline, summary, sigType, niche) {
  // All signals generate via the backend signal endpoint.
  // Content saves as pending and appears in "waiting for you" on Home.
  // Agent never leaves Home. No Studio. No broadcast panel.

  _signalGenerating = true;
  const signalZone = el("home-signal-zone");

  // Show immediate feedback on the Home screen
  if (signalZone) {
    signalZone.innerHTML = `
      <div style="padding:20px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);text-align:center;">
        <div style="font-size:14px;font-weight:600;color:var(--ink);margin-bottom:6px;">❖ Your Writer is on it…</div>
        <div style="font-size:12px;color:var(--ink-3);line-height:1.6;">Your Writer is turning this signal into a post in your voice.<br>It will appear in your review queue in a moment.</div>
      </div>`;
  }

  // niche was confirmed by agent in the picker modal before this function fired
  // Stage 2 — show Auditor message after 4 seconds while generation runs
  const auditorTimer = setTimeout(() => {
    if (signalZone) {
      signalZone.innerHTML = `
        <div style="padding:20px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);text-align:center;">
          <div style="font-size:14px;font-weight:600;color:var(--ink);margin-bottom:6px;">⚖ Your Auditor is reviewing it…</div>
          <div style="font-size:12px;color:var(--ink-3);line-height:1.6;">Your Writer finished the draft. Your Auditor is checking it for compliance before it reaches you.</div>
        </div>`;
    }
  }, 4000);

  try {
    const res = await authFetch(`${BACKEND_URL}/content/generate-from-signal`, {
      method: "POST",
      body: JSON.stringify({
        signal_id: signalId || null,
        headline:  headline || "",
        summary:   summary  || "",
        niche:     niche,
      })
    });

    clearTimeout(auditorTimer);
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();

    if (data.ok) {
      const newItemId = data.item_id;
      // Stage 3 — generation complete, show button that opens the post directly
      if (signalZone) {
        signalZone.innerHTML = `
          <div style="padding:20px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);text-align:center;">
            <div style="font-size:14px;font-weight:600;color:var(--green,#1a7a4a);margin-bottom:6px;">✓ Your Auditor cleared it.</div>
            <div style="font-size:12px;color:var(--ink-3);line-height:1.6;margin-bottom:12px;">Your post is ready for your review.</div>
            <button id="signal-review-btn" data-item-id="${newItemId}"
              style="display:inline-flex;align-items:center;gap:6px;padding:9px 18px;background:var(--gold);color:#fff;border:none;border-radius:var(--radius-pill);font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;">
              Review your post →
            </button>
          </div>`;
        // Wire the button after it renders
        setTimeout(() => {
          const reviewBtn = el("signal-review-btn");
          if (reviewBtn) {
            reviewBtn.addEventListener("click", async () => {
              _signalGenerating = false;
              // Force refresh to get the newly generated post
              const lib = await fetchLibrary(true);
              const item = lib.find(x => String(x.id) === String(newItemId));
              if (item) {
                _reviewModalOrigin = "home";
                navigateTo("library-panel");
                // Small delay to let library-panel render before opening modal
                setTimeout(() => openReviewModal(item), 150);
              } else {
                navigateTo("library-panel");
              }
            });
          }
        }, 100);
      }
      // Refresh pending queue in background so count updates
      setTimeout(() => renderHomeDashboard(), 400);
    } else {
      throw new Error("Generation returned ok:false");
    }
  } catch(err) {
    clearTimeout(auditorTimer);
    if (signalZone) {
      signalZone.innerHTML = `
        <div style="padding:16px;background:#fef2f2;border:1px solid #fecaca;border-radius:var(--radius-md);text-align:center;">
          <div style="font-size:13px;color:var(--red,#b91c1c);">⚠ Your Writer hit a snag. Please try again in a moment.</div>
        </div>`;
      _signalGenerating = false;
      setTimeout(() => renderHomeDashboard(), 4000);
    }
  }
}


// ─────────────────────────────────────────────
// SECTION 25A2: SCHEDULE MODE (5th Create mode)
// ─────────────────────────────────────────────

let _scheduleEditing = null; // niche being edited, or null for new

async function renderScheduleMode() {
  const zone = el("ce-schedule-zone"); if (!zone) return;
  zone.innerHTML = '<div style="font-size:13px;color:var(--ink-3);">Loading schedules…</div>';
  try {
    const res  = await authFetch(`${BACKEND_URL}/schedules`);
    const data = await res.json();
    const scheds = data.schedules || [];
    zone.innerHTML = "";

    // List existing schedules
    if (scheds.length) {
      const list = document.createElement("div");
      list.style.cssText = "display:flex;flex-direction:column;gap:10px;margin-bottom:20px;";
      scheds.forEach(s => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);flex-wrap:wrap;gap:8px;";
        const days = s.dayOfWeek ? (() => { try { return JSON.parse(s.dayOfWeek).join(", "); } catch(e){ return s.dayOfWeek; } })() : "";
        row.innerHTML = `
          <div>
            <div style="font-size:13px;font-weight:700;color:var(--ink);">${s.niche}</div>
            <div style="font-size:12px;color:var(--ink-3);margin-top:2px;">${s.frequency}${days ? " · " + days : ""} · ${s.timeOfDay} ${s.timezone || "America/Denver"}</div>
            ${s.nextRun ? `<div style="font-size:11px;color:var(--text-muted);margin-top:2px;">Next: ${new Date(s.nextRun+"Z").toLocaleString("en-US",{weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})}</div>` : ""}
          </div>
          <div style="display:flex;gap:8px;">
            <button class="btn-secondary" style="font-size:12px;padding:6px 14px;" onclick="schedEditStart('${s.niche.replace(/'/g,"\\'")}')">Edit</button>
            <button class="btn-secondary" style="font-size:12px;padding:6px 14px;color:var(--red);" onclick="schedDelete('${s.niche.replace(/'/g,"\\'")}')">Remove</button>
          </div>`;
        list.appendChild(row);
      });
      zone.appendChild(list);
    } else {
      const empty = document.createElement("div");
      empty.style.cssText = "font-size:13px;color:var(--ink-3);margin-bottom:16px;";
      empty.textContent = "No schedules set up yet. Add one below to let HomeBridge run on autopilot.";
      zone.appendChild(empty);
    }

    // Add/Edit form
    const saved = getSaved();
    const niches = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
    const form = document.createElement("div");
    form.id = "sched-form";
    form.style.cssText = "background:var(--blue-dim);border:1px solid var(--blue-border);border-radius:var(--radius-md);padding:18px 20px;";
    form.innerHTML = `
      <div style="font-size:13px;font-weight:700;color:var(--ink);margin-bottom:14px;" id="sched-form-title">Add a schedule</div>
      <div class="field-group" style="margin-bottom:12px;">
        <div class="field-label">Niche</div>
        <div class="select-wrapper">
          <select id="sched-niche">
            ${niches.map(n => `<option value="${n}">${n}</option>`).join("")}
          </select>
          <span class="select-arrow">▾</span>
        </div>
      </div>
      <div class="field-group" style="margin-bottom:12px;">
        <div class="field-label">Frequency</div>
        <div class="select-wrapper">
          <select id="sched-freq">
            <option value="daily">Daily</option>
            <option value="3x_week">3× per week</option>
            <option value="weekly" selected>Weekly</option>
            <option value="biweekly">Every 2 weeks</option>
            <option value="monthly">Monthly</option>
          </select>
          <span class="select-arrow">▾</span>
        </div>
      </div>
      <div class="field-group" style="margin-bottom:12px;">
        <div class="field-label">Days <span style="font-weight:400;font-size:11px;color:var(--ink-3);text-transform:none;letter-spacing:0;">optional — leave blank to run on any day</span></div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:4px;" id="sched-days">
          ${["mon","tue","wed","thu","fri","sat","sun"].map(d =>
            `<label style="display:flex;align-items:center;gap:5px;font-size:13px;cursor:pointer;">
              <input type="checkbox" class="sched-day-cb" value="${d}"> ${d.charAt(0).toUpperCase()+d.slice(1)}
            </label>`
          ).join("")}
        </div>
      </div>
      <div class="field-group" style="margin-bottom:12px;">
        <div class="field-label">Time</div>
        <input type="time" id="sched-time" value="08:00" style="padding:8px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:13px;background:var(--surface);color:var(--ink);" />
      </div>
      <div class="field-group" style="margin-bottom:16px;">
        <div class="field-label">Timezone</div>
        <div class="select-wrapper">
          <select id="sched-tz">
            <option value="America/New_York">Eastern</option>
            <option value="America/Chicago">Central</option>
            <option value="America/Denver" selected>Mountain</option>
            <option value="America/Los_Angeles">Pacific</option>
            <option value="America/Phoenix">Arizona</option>
            <option value="America/Anchorage">Alaska</option>
            <option value="Pacific/Honolulu">Hawaii</option>
          </select>
          <span class="select-arrow">▾</span>
        </div>
      </div>
      <div id="sched-error" class="inline-error"></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;">
        <button id="sched-save-btn" class="btn-primary" style="padding:10px 24px;" onclick="schedSave()">Save schedule</button>
        <button id="sched-cancel-btn" class="btn-secondary" style="padding:10px 18px;display:none;" onclick="schedCancelEdit()">Cancel</button>
      </div>`;
    zone.appendChild(form);
  } catch(e) {
    zone.innerHTML = `<div style="font-size:13px;color:var(--red);">Could not load schedules. Check your connection.</div>`;
  }
}

function schedEditStart(niche) {
  _scheduleEditing = niche;
  authFetch(`${BACKEND_URL}/schedules`).then(r=>r.json()).then(data => {
    const s = (data.schedules||[]).find(x => x.niche === niche);
    if (!s) return;
    const nicheEl = el("sched-niche"); if (nicheEl) nicheEl.value = s.niche;
    const freqEl  = el("sched-freq");  if (freqEl)  freqEl.value  = s.frequency;
    const timeEl  = el("sched-time");  if (timeEl)  timeEl.value  = s.timeOfDay || "08:00";
    const tzEl    = el("sched-tz");    if (tzEl)    tzEl.value    = s.timezone || "America/Denver";
    // Restore day checkboxes
    document.querySelectorAll(".sched-day-cb").forEach(cb => { cb.checked = false; });
    if (s.dayOfWeek) {
      try {
        const days = JSON.parse(s.dayOfWeek);
        days.forEach(d => {
          const cb = document.querySelector(`.sched-day-cb[value="${d}"]`);
          if (cb) cb.checked = true;
        });
      } catch(e) {}
    }
    const title  = el("sched-form-title");  if (title)  title.textContent  = `Editing: ${niche}`;
    const cancel = el("sched-cancel-btn");  if (cancel) cancel.style.display = "inline-flex";
    const saveBtn= el("sched-save-btn");    if (saveBtn)saveBtn.textContent  = "Update schedule";
    el("sched-form")?.scrollIntoView({ behavior:"smooth", block:"nearest" });
  });
}

function schedCancelEdit() {
  _scheduleEditing = null;
  renderScheduleMode();
}

async function schedSave() {
  const niche = el("sched-niche")?.value; if (!niche) { showMsg("sched-error","⚠ Please select a niche.",true); return; }
  const freq  = el("sched-freq")?.value  || "weekly";
  const time  = el("sched-time")?.value  || "08:00";
  const tz    = el("sched-tz")?.value    || "America/Denver";
  const days  = [...document.querySelectorAll(".sched-day-cb:checked")].map(cb => cb.value);
  const dayOfWeek = days.length ? JSON.stringify(days) : null;
  hideMsg("sched-error");
  const btn = el("sched-save-btn"); if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
  try {
    const res = await authFetch(`${BACKEND_URL}/schedules`, {
      method:"POST",
      body: JSON.stringify({ niche, frequency:freq, timeOfDay:time, timezone:tz, dayOfWeek })
    });
    if (!res.ok) throw new Error("Save failed");
    _scheduleEditing = null;
    renderScheduleMode();
  } catch(e) {
    showMsg("sched-error","⚠ Could not save schedule. Please try again.",true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = _scheduleEditing ? "Update schedule" : "Save schedule"; }
  }
}

async function schedDelete(niche) {
  if (!confirm(`Remove schedule for "${niche}"?`)) return;
  try {
    await authFetch(`${BACKEND_URL}/schedules/${encodeURIComponent(niche)}`, { method:"DELETE" });
    renderScheduleMode();
  } catch(e) {
    showToast("Could not remove schedule — please try again.");
  }
}



let _ceActiveMode = null;

function ceSelectMode(mode) {
  _ceActiveMode = mode;
  // Update card active states
  ["guided","idea","pulse","intel","schedule","freeform","video"].forEach(m => {
    el("ce-card-" + m)?.classList.toggle("active", m === mode);
  });
  // Show correct mode panel, hide others
  ["guided","idea","pulse","intel","schedule","freeform","video"].forEach(m => {
    const panel = el("ce-mode-" + m);
    if (panel) panel.style.display = m === mode ? "block" : "none";
  });
  // Identity summary — only relevant for guided and idea modes
  // where sub-niches directly shape what gets generated.
  // Hidden for pulse, intel, schedule, freeform, video — they don't need confirmation.
  const identityBlock = el("ce-identity-summary");
  if (identityBlock) {
    identityBlock.style.display = (mode === "guided" || mode === "idea") ? "block" : "none";
  }
  // Render niche chips / content for the active mode
  if (mode === "guided") {
    renderNicheSelector();
    const niche = activeNicheForGenerate || (getSaved().primaryNiches||[])[0] || null;
    populateSituationDropdown(niche);
    updatePersonaDropdown(niche);
    renderIdentitySummary();
    renderTrendsDisplay();
    // Reset persona and length to defaults on entry
    const personaSel = el("persona-select");
    if (personaSel) personaSel.selectedIndex = 0;
    const lengthSel = el("length-select");
    if (lengthSel) lengthSel.selectedIndex = 0;
    hideMsg("generate-error");
  }
  if (mode === "idea") {
    ceRenderNicheChips("idea-niche-chips");
    // Clear text field on entry so previous input doesn't persist
    const ideaInput = el("idea-input");
    if (ideaInput) ideaInput.value = "";
    hideMsg("idea-error");
  }
  if (mode === "pulse") {
    ceRenderNicheChips("pulse-niche-chips");
    // Init PDF tab as default, load saved reports, enable generate for text tab
    pulseSwitchTab("pdf");
    ceLoadSavedReports();
  }
  // intel mode: clear location field on entry, niche applied silently from profile
  if (mode === "intel") {
    const intelInput = el("intel-location-input");
    if (intelInput) intelInput.value = "";
    hideMsg("intel-error");
  }
  if (mode === "schedule") renderScheduleMode();
  // freeform mode: clear textarea and counter on entry
  if (mode === "freeform") {
    const ta = el("freeform-input");
    if (ta) { ta.value = ""; freeformUpdateCounter(ta); }
    hideMsg("freeform-error");
    freeformSwitchTab("personal");
  }
  // video mode: reset UI on entry and load usage counter
  if (mode === "video") {
    const ta = el("video-topic-input");
    if (ta) { ta.value = ""; videoUpdateCounter(ta); }
    hideMsg("video-error");
    const out = el("video-script-output");
    if (out) out.style.display = "none";
    const ind = el("video-generating-indicator");
    if (ind) ind.style.display = "none";
    // Load video usage counter — non-blocking, shows remaining renders
    _videoLoadUsageCounter();
  }
  // Scroll mode panel into view on mobile
  setTimeout(() => {
    const panel = el("ce-mode-" + mode);
    if (panel && window.innerWidth < 768) panel.scrollIntoView({ behavior:"smooth", block:"nearest" });
  }, 100);
}


// ── FREEFORM (Quick Post) — counter, sanitizer, generate listener ──────────

const FREEFORM_MAX     = 500;
const FREEFORM_MIN     = 10;
const FREEFORM_WARN_AT = 450;

// Injection patterns to strip silently before sending to backend
const _INJECTION_PATTERNS = [
  /ignore\s+(previous|prior|all|your)\s+instructions?/gi,
  /you\s+are\s+now\s+a/gi,
  /forget\s+(everything|your\s+instructions?)/gi,
  /disregard\s+(previous|prior|all)/gi,
  /act\s+as\s+(if\s+you\s+are|a)\s+/gi,
  /new\s+instructions?:/gi,
  /system\s*prompt/gi,
  /<\s*script[^>]*>/gi,
];

// Gibberish / abusive check — true if input looks like garbage or abuse
function _freeformIsGibberish(text) {
  if (!text || text.trim().length === 0) return true;
  // Repeating single char (e.g. "aaaaaaaaaa")
  if (/^(.)\1{9,}$/.test(text.trim())) return true;
  // No vowels at all in a long string — keyboard mashing
  const stripped = text.replace(/\s/g, "");
  if (stripped.length > 15 && !/[aeiouAEIOU]/.test(stripped)) return true;
  // Ratio of letters to total chars — pure symbols/numbers not a thought
  const letters = (text.match(/[a-zA-Z]/g) || []).length;
  if (text.length > 20 && letters / text.length < 0.3) return true;
  return false;
}

// Strip injection patterns silently
function _freeformSanitize(text) {
  let cleaned = text;
  _INJECTION_PATTERNS.forEach(pattern => {
    cleaned = cleaned.replace(pattern, "");
  });
  return cleaned.trim().slice(0, FREEFORM_MAX);
}

// Update the live character counter
function freeformUpdateCounter(textarea) {
  const counter = el("freeform-counter");
  if (!counter) return;
  const len = (textarea.value || "").length;
  counter.textContent = `${len} / ${FREEFORM_MAX}`;
  counter.style.color = len >= FREEFORM_WARN_AT ? "var(--red, #e53e3e)" : "var(--ink-3)";
}

// Wire counter to input event — done once on DOMContentLoaded via delegation
document.addEventListener("input", e => {
  if (e.target && e.target.id === "freeform-input") {
    freeformUpdateCounter(e.target);
  }
});

// Generate listener

// Track active freeform tab
let _freeformTab = "personal";  // "personal" | "connect"

function freeformSwitchTab(tab) {
  _freeformTab = tab;
  const personal = el("freeform-tab-personal");
  const connect  = el("freeform-tab-connect");
  if (personal) personal.classList.toggle("pulse-tab-active", tab === "personal");
  if (connect)  connect.classList.toggle("pulse-tab-active", tab === "connect");
}

el("freeform-generate-btn")?.addEventListener("click", async () => {
  const ta    = el("freeform-input");
  const raw   = (ta?.value || "").trim();
  const niche = ceSelectedNiche || (getSaved().primaryNiches||[])[0] || "Residential Buying & Selling";

  hideMsg("freeform-error");

  // Validation
  if (raw.length < FREEFORM_MIN) {
    showMsg("freeform-error", "⚠ Give The Writer a little more to work with — a sentence or two is enough.", true);
    return;
  }
  if (_freeformIsGibberish(raw)) {
    showMsg("freeform-error", "⚠ That doesn't look like a thought — try again with something on your mind.", true);
    return;
  }

  // Sanitize silently
  const thought = _freeformSanitize(raw);

  const btn = el("freeform-generate-btn");
  const ind = el("freeform-generating-indicator");
  btn.disabled = true; btn.textContent = "⚡ Finding the story…";
  if (ind) ind.style.display = "block";

  try {
    const saved = getSaved();
    const payload = {
      identity:       { primaryCategories:[niche], subNichesByCategory:{}, trendPreferences: saved.trends||[] },
      agentProfile:   ceAgentProfilePayload(),
      situation:      thought,
      persona:        null,
      tone:           null,
      length:         "medium",
      content_mode:   "agent",
      generation_mode:"freeform",
      personal_mode: _freeformTab === "personal",
    };
    const res  = await authFetch(`${BACKEND_URL}/content/generate-content`, { method:"POST", body:JSON.stringify(payload) });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    await ceHandleResult(data, niche);
  } catch(err) {
    if (err.message !== "Session expired") showMsg("freeform-error","⚠ Generation failed. Please check your connection and try again.",true);
  } finally {
    btn.disabled = false; btn.textContent = "⚡ Turn This Into a Post";
    if (ind) ind.style.display = "none";
  }
});

// ── VIDEO / CREATE VIDEO MODE ─────────────────────────────────────────────────

const VIDEO_TOPIC_MAX  = 300;
const VIDEO_TOPIC_MIN  = 10;
let _videoSelectedTone  = "Warm";
let _videoLibraryItem   = null;
let _videoActivePath    = null;   // 'analyst' | 'idea'
let _videoSelectedTopic = null;   // topic chosen from analyst suggestions or typed

function videoUpdateCounter(textarea) {
  const counter = el("video-topic-counter");
  if (!counter) return;
  const len = (textarea?.value || "").length;
  counter.textContent = `${len} / ${VIDEO_TOPIC_MAX}`;
  counter.style.color = len >= VIDEO_TOPIC_MAX - 20 ? "var(--red,#e53e3e)" : "var(--ink-3)";
}

function videoSelectPath(path) {
  _videoActivePath    = path;
  _videoSelectedTopic = null;

  const analystCard = el("video-path-analyst-card");
  const ideaCard    = el("video-path-idea-card");
  const analystPath = el("video-analyst-path");
  const ideaPath    = el("video-idea-path");
  const toneSection = el("video-tone-section");
  const output      = el("video-script-output");
  const genInd      = el("video-generating-indicator");

  // Hide output and indicator on path switch
  if (output)  output.style.display  = "none";
  if (genInd)  genInd.style.display  = "none";
  hideMsg("video-error");

  if (path === "analyst") {
    if (analystCard) { analystCard.style.borderColor = "var(--gold)"; analystCard.style.background = "var(--gold-dim)"; }
    if (ideaCard)    { ideaCard.style.borderColor = "var(--border)";  ideaCard.style.background = "var(--white)"; }
    if (analystPath) analystPath.style.display = "block";
    if (ideaPath)    ideaPath.style.display    = "none";
    if (toneSection) toneSection.style.display = "none";
    _videoFetchTopics();
  } else {
    if (ideaCard)    { ideaCard.style.borderColor = "var(--gold)";    ideaCard.style.background = "var(--gold-dim)"; }
    if (analystCard) { analystCard.style.borderColor = "var(--border)"; analystCard.style.background = "var(--white)"; }
    if (ideaPath)    ideaPath.style.display    = "block";
    if (analystPath) analystPath.style.display = "none";
    if (toneSection) toneSection.style.display = "block";
    const ta = el("video-topic-input");
    if (ta) { ta.value = ""; videoUpdateCounter(ta); ta.focus(); }
  }
}

async function _videoFetchTopics() {
  const container = el("video-analyst-topics");
  const loading   = el("video-analyst-loading");
  const toneSection = el("video-tone-section");
  if (!container) return;

  if (loading)  loading.style.display  = "block";
  if (toneSection) toneSection.style.display = "none";
  container.innerHTML = "";
  _videoSelectedTopic = null;

  const saved  = getSaved();
  const niche  = ceSelectedNiche || (saved.primaryNiches||[])[0] || "real estate";
  const market = getMarketContext() || "their local market";

  try {
    const res = await authFetch(`${BACKEND_URL}/content/video-topics`, {
      method: "POST",
      body: JSON.stringify({ niche, market, agentProfile: ceAgentProfilePayload() }),
    });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    const topics = data.topics || [];

    if (!topics.length) throw new Error("No topics returned");

    container.innerHTML = "";
    topics.forEach((topic, i) => {
      const card = document.createElement("div");
      card.style.cssText = "padding:14px 16px;border:1.5px solid var(--border);border-radius:12px;cursor:pointer;transition:all 0.15s;background:var(--white);";
      card.innerHTML = `
        <div style="display:flex;align-items:flex-start;gap:10px;">
          <div style="font-size:11px;font-weight:700;color:var(--gold);flex-shrink:0;padding-top:2px;">TOPIC ${i+1}</div>
          <div style="font-size:13px;color:var(--ink);line-height:1.5;font-weight:500;">${topic}</div>
        </div>`;
      card.addEventListener("mouseenter", () => { card.style.borderColor = "var(--gold)"; card.style.background = "var(--gold-dim)"; });
      card.addEventListener("mouseleave", () => {
        if (_videoSelectedTopic !== topic) { card.style.borderColor = "var(--border)"; card.style.background = "var(--white)"; }
      });
      card.addEventListener("click", () => {
        // Deselect all
        container.querySelectorAll("div[data-topic]").forEach(c => {
          c.style.borderColor = "var(--border)"; c.style.background = "var(--white)";
        });
        card.dataset.topic = topic;
        card.style.borderColor = "var(--gold)";
        card.style.background  = "var(--gold-dim)";
        _videoSelectedTopic = topic;
        if (toneSection) toneSection.style.display = "block";
        // Scroll tone into view
        setTimeout(() => toneSection?.scrollIntoView({ behavior:"smooth", block:"nearest" }), 100);
      });
      card.dataset.topic = "";
      container.appendChild(card);
    });

  } catch(err) {
    container.innerHTML = `<div style="font-size:13px;color:var(--ink-3);font-style:italic;">Couldn't load suggestions — tap "Find different topics" to try again.</div>`;
  } finally {
    if (loading) loading.style.display = "none";
  }
}

function videoResetToStart() {
  _videoActivePath    = null;
  _videoSelectedTopic = null;
  _videoLibraryItem   = null;

  const analystCard = el("video-path-analyst-card");
  const ideaCard    = el("video-path-idea-card");
  if (analystCard) { analystCard.style.borderColor = "var(--border)"; analystCard.style.background = "var(--white)"; }
  if (ideaCard)    { ideaCard.style.borderColor    = "var(--border)"; ideaCard.style.background    = "var(--white)"; }

  const ids = ["video-analyst-path","video-idea-path","video-tone-section","video-script-output","video-generating-indicator"];
  ids.forEach(id => { const e = el(id); if (e) e.style.display = "none"; });
  hideMsg("video-error");
  const ta = el("video-topic-input");
  if (ta) { ta.value = ""; videoUpdateCounter(ta); }
}

// Wire up video mode on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => {
  const ta = el("video-topic-input");
  if (ta) ta.addEventListener("input", e => {
    videoUpdateCounter(e.target);
    // Show tone section once agent starts typing
    const toneSection = el("video-tone-section");
    if (toneSection && e.target.value.trim().length > 0) toneSection.style.display = "block";
    else if (toneSection && e.target.value.trim().length === 0) toneSection.style.display = "none";
  });

  // Tone chip selection
  document.querySelectorAll(".video-tone-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".video-tone-chip").forEach(c => c.classList.remove("selected"));
      chip.classList.add("selected");
      _videoSelectedTone = chip.dataset.tone || "Warm";
    });
  });

  el("video-generate-btn")?.addEventListener("click", () => _videoGenerate());
  el("video-regen-btn")?.addEventListener("click",    () => _videoGenerate());
  el("video-approve-btn")?.addEventListener("click",  () => _videoApprove());

  el("video-copy-btn")?.addEventListener("click", () => {
    const txt = el("video-script-text")?.value || "";
    if (!txt) return;
    navigator.clipboard.writeText(txt).then(() => {
      const btn = el("video-copy-btn");
      if (btn) { btn.textContent = "Copied!"; setTimeout(() => btn.textContent = "Copy script", 2000); }
    }).catch(() => showToast("Copy failed — please select and copy manually."));
  });
});

async function _videoGenerate() {
  // Resolve topic from active path
  let topic = "";
  if (_videoActivePath === "analyst") {
    topic = _videoSelectedTopic || "";
    if (!topic) {
      showMsg("video-error", "⚠ Tap a topic from the Analyst's suggestions first.", true);
      return;
    }
  } else {
    topic = (el("video-topic-input")?.value || "").trim();
    if (topic.length < VIDEO_TOPIC_MIN) {
      showMsg("video-error", "⚠ Give The Writer a topic to work with — a sentence is enough.", true);
      return;
    }
  }

  hideMsg("video-error");

  const saved  = getSaved();
  const niche  = ceSelectedNiche || (saved.primaryNiches||[])[0] || "real estate";

  const btn = el("video-generate-btn");
  const ind = el("video-generating-indicator");
  const out = el("video-script-output");
  if (btn) { btn.disabled = true; btn.textContent = "✍️ Writing your script…"; }
  if (ind) ind.style.display = "block";
  if (out) out.style.display = "none";

  try {
    const payload = {
      topic,
      tone:         _videoSelectedTone,
      niche,
      agentProfile: ceAgentProfilePayload(),
    };
    const res = await authFetch(`${BACKEND_URL}/content/video-script`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Status ${res.status}`);
    }
    const data = await res.json();

    const scriptEl = el("video-script-text");
    if (scriptEl) scriptEl.value = data.script || "";

    const wcEl = el("video-word-count");
    if (wcEl) wcEl.textContent = `${data.word_count || 0} words`;

    _videoRenderCompliance(data.compliance || {});

    const isDemo = localStorage.getItem("hb_demo_mode") === "true";
    if (!isDemo) {
      try {
        _videoLibraryItem = await apiSaveLibraryItem(niche, {
          headline:     `Video — ${topic.slice(0, 60)}`,
          post:         data.script || "",
          content_type: "video_script",
          topic,
          tone:         _videoSelectedTone,
          word_count:   data.word_count || 0,
        }, data.compliance || {});
      } catch(saveErr) {
        console.warn("Video library save failed:", saveErr);
        _videoLibraryItem = null;
      }
    } else {
      _videoLibraryItem = { id: "demo-video-" + Date.now() };
    }

    if (out) out.style.display = "block";
    if (ind) ind.style.display = "none";

  } catch(err) {
    if (ind) ind.style.display = "none";
    if (err.message !== "Session expired") {
      showMsg("video-error", `⚠ Script generation failed — ${err.message || "please try again."}`, true);
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "✍️ Write My Script"; }
  }
}

function _videoRenderCompliance(comp) {
  const bar  = el("video-compliance-bar");
  const dot  = el("video-comp-dot");
  const text = el("video-comp-text");
  if (!bar || !dot || !text) return;

  const status = (comp.overallStatus || comp.overall_verdict || "clear").toLowerCase();
  const notes  = Array.isArray(comp.notes) ? comp.notes.filter(Boolean) : [];

  if (status === "clear" || status === "pass") {
    bar.style.cssText    = "display:flex;padding:10px 14px;border-radius:8px;margin-bottom:12px;align-items:flex-start;gap:8px;background:var(--green-dim);border:1px solid rgba(26,122,74,0.2);";
    dot.style.background = "var(--green)";
    text.style.color     = "var(--green)";
    text.textContent     = "Compliance review passed. Ready to approve.";
  } else {
    bar.style.cssText    = "display:flex;padding:10px 14px;border-radius:8px;margin-bottom:12px;align-items:flex-start;gap:8px;background:var(--amber-dim);border:1px solid rgba(180,83,9,0.2);";
    dot.style.background = "var(--amber)";
    text.style.color     = "var(--amber)";
    text.textContent     = notes.length
      ? `Compliance notes: ${notes.join(" · ")}`
      : "Review flagged — check your script before approving.";
  }
}

async function _videoApprove() {
  if (!_videoLibraryItem || !_videoLibraryItem.id) {
    showToast("⚠ No script to approve — generate one first.");
    return;
  }
  const btn = el("video-approve-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  try {
    const editedScript = el("video-script-text")?.value || "";
    const topic        = _videoSelectedTopic || (el("video-topic-input")?.value || "").trim();

    await apiPatchLibraryItem(_videoLibraryItem.id, {
      status:     "approved",
      approvedAt: new Date().toISOString(),
      content: {
        headline:     `Video — ${topic.slice(0,60)}`,
        post:         editedScript,
        content_type: "video_script",
        tone:         _videoSelectedTone,
        word_count:   editedScript.split(/\s+/).filter(Boolean).length,
      },
    });

    showToast("✓ Video script approved and saved to Records.");
    videoResetToStart();
    _videoLibraryItem = null;

  } catch(err) {
    if (err.message !== "Session expired") showToast("⚠ Approval failed — please try again.");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "✓ Approve & Save to Records"; }
  }
}

// ── END CREATE VIDEO ──────────────────────────────────────────────────────────

// ── Video usage counter ───────────────────────────────────────────────────────
// Fetches /video/limit and updates the counter element in the video panel.
// Called when the agent enters video mode. Non-blocking — silent on failure.
async function _videoLoadUsageCounter() {
  const counterEl = el("video-usage-counter");
  if (!counterEl) return;
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  if (isDemo) {
    counterEl.textContent = "Demo mode — video rendering disabled";
    counterEl.style.display = "block";
    return;
  }
  try {
    const res = await authFetch(`${BACKEND_URL}/video/limit`);
    if (!res.ok) { counterEl.style.display = "none"; return; }
    const data = await res.json();
    if (!data.plan_allows) {
      counterEl.textContent = "Video generation is available on Starter plans and above.";
      counterEl.style.display = "block";
      return;
    }
    const used  = data.videos_used  || 0;
    const limit = data.videos_limit || 0;
    const resets = data.resets_on   || "";
    const remaining = Math.max(0, limit - used);
    let text = `${used} of ${limit} video render${limit !== 1 ? "s" : ""} used this month`;
    if (resets) text += ` · Resets ${resets}`;
    counterEl.textContent = text;
    counterEl.style.display = "block";
    counterEl.style.color = remaining === 0 ? "var(--red,#c0392b)" : "var(--ink-4)";
  } catch(e) {
    counterEl.style.display = "none";
  }
}


// ── VIDEO RENDER PIPELINE — Session 49/50 ────────────────────────────────────
//
// Stage 2: After a script is generated and approved, the agent can generate
// an avatar video. Their profile photo is animated with lip sync to the script.
//
// State:
//   _videoJobId        — internal job ID returned by POST /video/render
//   _videoPollTimer    — setInterval handle for status polling
//   _videoRenderScript — the script text being rendered (for re-use on retry)
//   _videoRenderItemId — library_item_id tied to this render
//
// Flow:
//   1. Agent taps "Generate My Video" on the script output
//   2. _videoRenderAvatar() — checks limit, submits render, starts polling
//   3. _videoPollStatus()   — polls /video/status every 5s, updates UI
//   4. On completion        — shows inline video player, approve/discard buttons
//   5. _videoApproveRendered() — agent approves, video URL saved to library item

let _videoJobId        = null;
let _videoPollTimer    = null;
let _videoRenderScript = null;
let _videoRenderItemId = null;

async function _videoRenderAvatar() {
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  if (isDemo) {
    showToast("Video rendering is not available in demo mode.");
    return;
  }

  const script = el("video-script-text")?.value?.trim() || "";
  if (!script) {
    showToast("⚠ No script to render. Generate a script first.");
    return;
  }

  // Check if agent has a profile photo in localStorage as a quick pre-check
  // (backend will do the authoritative check, this just saves a round trip)
  const hasLocalPhoto = !!localStorage.getItem("hb_profile_photo");
  if (!hasLocalPhoto) {
    showToast("⚠ Upload your profile photo first. Tap your initials in the top-right corner, then 'Upload Photo'.");
    return;
  }

  _videoRenderScript = script;
  _videoRenderItemId = _videoLibraryItem?.id || null;

  // Show render UI state
  _videoSetRenderState("submitting");

  try {
    const res = await authFetch(`${BACKEND_URL}/video/render`, {
      method: "POST",
      body: JSON.stringify({
        script:          script,
        library_item_id: typeof _videoRenderItemId === "number" ? _videoRenderItemId : null,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      const detail = data.detail || {};
      const errCode = typeof detail === "object" ? detail.error : null;

      if (errCode === "plan_no_video") {
        _videoSetRenderState("idle");
        _videoShowRenderError("Video generation is available on Starter plans and above. Upgrade your plan to unlock this feature.");
        return;
      }
      if (errCode === "video_limit_reached") {
        _videoSetRenderState("idle");
        _videoShowRenderError(`${detail.message || "Monthly video limit reached."}`);
        return;
      }
      if (errCode === "no_photo") {
        _videoSetRenderState("idle");
        _videoShowRenderError("Upload your profile photo first. Tap your initials in the top-right corner → 'Upload Photo', then try again.");
        return;
      }
      throw new Error(typeof detail === "string" ? detail : (detail.message || `Status ${res.status}`));
    }

    _videoJobId = data.job_id;
    _videoSetRenderState("processing");

    // Start polling every 5 seconds
    if (_videoPollTimer) clearInterval(_videoPollTimer);
    _videoPollTimer = setInterval(() => _videoPollStatus(), 5000);

  } catch(err) {
    _videoSetRenderState("idle");
    if (err.message !== "Session expired") {
      _videoShowRenderError(`⚠ Video generation failed — ${err.message || "please try again."}`);
    }
  }
}


async function _videoPollStatus() {
  if (!_videoJobId) {
    if (_videoPollTimer) { clearInterval(_videoPollTimer); _videoPollTimer = null; }
    return;
  }

  try {
    const res = await authFetch(`${BACKEND_URL}/video/status/${_videoJobId}`);
    if (!res.ok) return; // silent — keep polling

    const data = await res.json();
    const status = data.status || "processing";

    if (status === "completed" && data.video_url) {
      // Stop polling
      if (_videoPollTimer) { clearInterval(_videoPollTimer); _videoPollTimer = null; }
      _videoSetRenderState("completed", data.video_url);

    } else if (status === "failed") {
      if (_videoPollTimer) { clearInterval(_videoPollTimer); _videoPollTimer = null; }
      _videoSetRenderState("idle");
      _videoShowRenderError(`⚠ Video generation failed${data.error ? " — " + data.error : ""}. Please try again.`);
    }
    // pending/processing — keep polling
  } catch(err) {
    // Network error during poll — keep polling silently
    console.warn("[Video] Poll error (retrying):", err.message);
  }
}


async function _videoApproveRendered() {
  const videoUrl = el("video-player")?.src || el("video-player")?.getAttribute("src") || "";
  if (!videoUrl) {
    showToast("⚠ No video to approve.");
    return;
  }

  const btn = el("video-render-approve-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  try {
    // If we have a library item, patch it with the video URL
    if (_videoRenderItemId && typeof _videoRenderItemId === "number" && !String(_videoRenderItemId).startsWith("demo")) {
      await apiPatchLibraryItem(_videoRenderItemId, {
        status:     "approved",
        approvedAt: new Date().toISOString(),
        content: {
          headline:     (el("video-script-text") ? `Video — ${(_videoRenderScript||"").slice(0,60)}` : "Video"),
          post:         _videoRenderScript || "",
          content_type: "video_script",
          video_url:    videoUrl,
        },
      });
    }

    showToast("✓ Video approved and saved to Records.");
    _videoResetRenderState();
    videoResetToStart();
    _videoLibraryItem  = null;
    _videoJobId        = null;
    _videoRenderScript = null;
    _videoRenderItemId = null;

  } catch(err) {
    if (err.message !== "Session expired") {
      showToast("⚠ Approval failed — please try again.");
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "✓ Approve & Save to Records"; }
  }
}


function _videoDiscardRendered() {
  if (!confirm("Discard this video? This uses one of your monthly video renders.")) return;
  _videoResetRenderState();
  showToast("Video discarded. Your script is still saved below.");
}


// ── Video render UI state management ─────────────────────────────────────────

function _videoSetRenderState(state, videoUrl) {
  const submitBtn    = el("video-render-btn");
  const indicator    = el("video-render-indicator");
  const playerWrap   = el("video-render-player-wrap");
  const player       = el("video-player");
  const renderError  = el("video-render-error");

  // Hide error on any state change
  if (renderError) renderError.style.display = "none";

  if (state === "idle") {
    if (submitBtn)   { submitBtn.disabled = false; submitBtn.textContent = "🎬 Generate My Video"; }
    if (indicator)   indicator.style.display = "none";
    if (playerWrap)  playerWrap.style.display = "none";
  } else if (state === "submitting") {
    if (submitBtn)   { submitBtn.disabled = true;  submitBtn.textContent = "Submitting…"; }
    if (indicator)   { indicator.style.display = "block"; indicator.querySelector(".video-render-status-text") && (indicator.querySelector(".video-render-status-text").textContent = "Submitting your request…"); }
    if (playerWrap)  playerWrap.style.display = "none";
  } else if (state === "processing") {
    if (submitBtn)   { submitBtn.disabled = true;  submitBtn.textContent = "Generating…"; }
    if (indicator)   {
      indicator.style.display = "block";
      const statusText = indicator.querySelector(".video-render-status-text");
      if (statusText) statusText.textContent = "Your video is being generated. This usually takes 1–3 minutes…";
    }
    if (playerWrap)  playerWrap.style.display = "none";
  } else if (state === "completed") {
    if (submitBtn)   { submitBtn.disabled = false; submitBtn.textContent = "🎬 Generate Another Video"; }
    if (indicator)   indicator.style.display = "none";
    if (playerWrap)  {
      playerWrap.style.display = "block";
      if (player && videoUrl) {
        player.src = videoUrl;
        player.load();
      }
    }
  }
}


function _videoResetRenderState() {
  _videoJobId        = null;
  _videoRenderScript = null;
  _videoRenderItemId = null;
  if (_videoPollTimer) { clearInterval(_videoPollTimer); _videoPollTimer = null; }
  _videoSetRenderState("idle");
}


function _videoShowRenderError(message) {
  const el_err = el("video-render-error");
  if (!el_err) { showToast(message); return; }
  el_err.textContent = message;
  el_err.style.display = "block";
}


// Wire up video render buttons on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => {
  el("video-render-btn")?.addEventListener("click",         () => _videoRenderAvatar());
  el("video-render-approve-btn")?.addEventListener("click", () => _videoApproveRendered());
  el("video-render-discard-btn")?.addEventListener("click", () => _videoDiscardRendered());
});

// ── END VIDEO RENDER PIPELINE ─────────────────────────────────────────────────


// ── VOICE IDENTITY — Session 51 ──────────────────────────────────────────────
//
// Manages the agent's voice setup UI inside the Identity panel.
// Voice is used at video render time — LMNT synthesizes the script into audio
// using the agent's cloned voice, which HeyGen uses instead of a stock voice.
//
// LMNT is infrastructure. Never mentioned in UI copy.
// Agent-facing language: "Your Voice", "Set up your voice", "Voice is ready."
//
// Three UI states rendered into #voice-setup-section:
//   STATE 1 — No consent yet:
//     Show explanation + "Set Up My Voice" button → triggers consent modal
//   STATE 2 — Consent given, no voice yet:
//     Show recording UI (MediaRecorder) + file upload alternative
//   STATE 3 — Voice is set up:
//     Show "Your voice is ready" confirmation + "Remove voice" link
//
// Flow:
//   _voiceLoadStatus()      → fetches /voice/status, renders correct state
//   _voiceShowConsentModal() → shows consent modal
//   _voiceRecordConsent()   → POST /voice/consent, then re-renders to state 2
//   _voiceStartRecording()  → starts MediaRecorder, shows timer
//   _voiceStopRecording()   → stops recorder, shows preview + submit button
//   _voiceSubmitRecording() → POST /voice/setup with audio blob
//   _voiceDelete()          → DELETE /voice/setup, re-renders to state 1
//
// State is never cached — always fetched fresh from backend on panel open.

let _voiceMediaRecorder   = null;
let _voiceAudioChunks     = [];
let _voiceRecordingTimer  = null;
let _voiceRecordingSeconds = 0;
let _voiceAudioBlob       = null;


async function _voiceLoadStatus() {
  const section = el("voice-setup-section");
  if (!section) return;

  // Demo mode — show placeholder, no API calls
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";
  if (isDemo) {
    section.innerHTML = _voiceRenderState("ready_demo");
    return;
  }

  section.innerHTML = `<div style="font-size:13px;color:var(--ink-3);padding:12px 0;">Loading…</div>`;

  try {
    const res = await authFetch(`${BACKEND_URL}/voice/status`);
    if (!res.ok) { section.innerHTML = _voiceRenderState("error"); return; }
    const data = await res.json();

    if (data.has_voice) {
      section.innerHTML = _voiceRenderState("ready");
    } else if (data.has_consent) {
      section.innerHTML = _voiceRenderState("record");
      _voiceWireRecordUI();
    } else {
      section.innerHTML = _voiceRenderState("prompt");
    }
  } catch(e) {
    section.innerHTML = _voiceRenderState("error");
  }
}


function _voiceRenderState(state) {
  // Shared card wrapper style
  const card = (inner) => `
    <div style="background:var(--white);border:1px solid var(--border);border-radius:12px;padding:20px 22px;margin-top:20px;">
      ${inner}
    </div>`;

  const sectionHeader = `
    <div style="font-size:13px;font-weight:700;color:var(--ink);letter-spacing:0.04em;text-transform:uppercase;margin-bottom:14px;">Your Voice</div>`;

  if (state === "prompt") {
    return card(`
      ${sectionHeader}
      <div style="font-size:13px;color:var(--ink-2);line-height:1.6;margin-bottom:16px;">
        Record a short voice sample and your videos will sound exactly like you — not a generic voice.
        Takes about 2–3 minutes and only needs to be done once.
      </div>
      <button onclick="_voiceShowConsentModal()"
        style="padding:10px 20px;background:var(--gold);color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;">
        Set Up My Voice →
      </button>`);
  }

  if (state === "record") {
    return card(`
      ${sectionHeader}
      <div style="font-size:13px;color:var(--ink-2);line-height:1.6;margin-bottom:16px;">
        Record 2–3 minutes of yourself speaking naturally. Read from a script, describe a listing,
        explain a market trend — anything in your own words. Speak clearly and avoid background noise.
      </div>

      <div id="voice-record-controls">
        <button id="voice-record-btn" onclick="_voiceStartRecording()"
          style="padding:10px 20px;background:var(--gold);color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;margin-right:10px;">
          ● Start Recording
        </button>
        <span id="voice-record-timer" style="font-size:13px;color:var(--ink-3);display:none;">0:00</span>
      </div>

      <div id="voice-preview-section" style="display:none;margin-top:16px;">
        <div style="font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:8px;">Preview your recording:</div>
        <audio id="voice-preview-player" controls style="width:100%;height:36px;"></audio>
        <div style="margin-top:14px;display:flex;gap:10px;align-items:center;">
          <button id="voice-submit-btn" onclick="_voiceSubmitRecording()"
            style="padding:10px 20px;background:var(--gold);color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;">
            Save My Voice
          </button>
          <button onclick="_voiceStartRecording()"
            style="padding:10px 16px;background:none;border:1px solid var(--border);border-radius:8px;font-size:13px;color:var(--ink-2);cursor:pointer;font-family:inherit;">
            Re-record
          </button>
        </div>
      </div>

      <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--border);">
        <div style="font-size:12px;color:var(--ink-3);margin-bottom:8px;">Or upload an audio file (MP3, WAV, or M4A):</div>
        <input type="file" id="voice-file-input" accept="audio/mp3,audio/wav,audio/m4a,audio/mpeg,audio/x-m4a,audio/*"
          onchange="_voiceHandleFileUpload(event)"
          style="font-size:12px;color:var(--ink-2);">
      </div>

      <div id="voice-setup-error" style="display:none;margin-top:12px;font-size:13px;color:var(--red,#c0392b);
        background:var(--red-dim,#fef2f2);border:1px solid rgba(192,57,43,0.2);border-radius:8px;padding:10px 14px;line-height:1.5;"></div>`);
  }

  if (state === "ready") {
    return card(`
      ${sectionHeader}
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
        <div style="width:8px;height:8px;border-radius:50%;background:var(--green,#1A7A4A);flex-shrink:0;"></div>
        <div style="font-size:13px;font-weight:600;color:var(--ink);">Your voice is ready.</div>
      </div>
      <div style="font-size:13px;color:var(--ink-3);line-height:1.6;margin-bottom:14px;">
        Your videos will use your own voice. To replace it, remove it and record a new sample.
      </div>
      <button onclick="_voiceDelete(this)"
        style="padding:8px 14px;background:none;border:1px solid var(--border);border-radius:8px;font-size:12px;color:var(--ink-3);cursor:pointer;font-family:inherit;">
        Remove my voice
      </button>`);
  }

  if (state === "ready_demo") {
    return card(`
      ${sectionHeader}
      <div style="font-size:13px;color:var(--ink-3);line-height:1.6;">
        Voice setup is available in your live account. Demo mode shows a preview only.
      </div>`);
  }

  // error fallback
  return card(`
    ${sectionHeader}
    <div style="font-size:13px;color:var(--ink-3);">Could not load voice status. Refresh the page to try again.</div>`);
}


function _voiceWireRecordUI() {
  // Nothing to wire on initial render — buttons use inline onclick.
  // This function is a hook for any future wiring needs.
}


function _voiceShowConsentModal() {
  // Build modal
  const overlay = document.createElement("div");
  overlay.id = "voice-consent-overlay";
  overlay.style.cssText = `
    position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9000;
    display:flex;align-items:center;justify-content:center;padding:24px;`;

  overlay.innerHTML = `
    <div style="background:var(--white);border-radius:16px;padding:32px 28px;max-width:460px;width:100%;box-shadow:0 8px 40px rgba(0,0,0,0.18);">
      <div style="font-size:17px;font-weight:700;color:var(--ink);margin-bottom:14px;">Before you record your voice</div>
      <div style="font-size:13px;color:var(--ink-2);line-height:1.7;margin-bottom:20px;">
        Your voice recording will be used to create a personal voice model.
        This model is used exclusively to generate the audio track in your videos —
        nothing else. Your voice data is stored securely and will never be shared.
        You can remove it at any time from the Identity panel.
      </div>
      <label style="display:flex;align-items:flex-start;gap:10px;margin-bottom:24px;cursor:pointer;">
        <input type="checkbox" id="voice-consent-check"
          style="margin-top:3px;width:15px;height:15px;accent-color:var(--gold);flex-shrink:0;">
        <span style="font-size:13px;color:var(--ink-2);line-height:1.6;">
          I understand and consent to my voice recording being used to create a personal voice model for my videos.
        </span>
      </label>
      <div style="display:flex;gap:10px;">
        <button id="voice-consent-confirm-btn"
          onclick="_voiceRecordConsent()"
          disabled
          style="flex:1;padding:12px;background:var(--gold);color:#fff;border:none;border-radius:8px;
            font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;opacity:0.4;">
          Continue →
        </button>
        <button onclick="document.getElementById('voice-consent-overlay')?.remove()"
          style="padding:12px 20px;background:none;border:1px solid var(--border);border-radius:8px;
            font-size:14px;color:var(--ink-2);cursor:pointer;font-family:inherit;">
          Cancel
        </button>
      </div>
    </div>`;

  document.body.appendChild(overlay);

  // Enable confirm button only when checkbox is checked
  const check = overlay.querySelector("#voice-consent-check");
  const btn   = overlay.querySelector("#voice-consent-confirm-btn");
  check.addEventListener("change", () => {
    btn.disabled = !check.checked;
    btn.style.opacity = check.checked ? "1" : "0.4";
    btn.style.cursor  = check.checked ? "pointer" : "default";
  });
}


async function _voiceRecordConsent() {
  const btn = el("voice-consent-confirm-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  try {
    const res = await authFetch(`${BACKEND_URL}/voice/consent`, { method: "POST" });
    if (!res.ok) throw new Error("Consent save failed");
    // Remove modal and reload the voice section to state 2
    el("voice-consent-overlay")?.remove();
    await _voiceLoadStatus();
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = "Continue →"; }
    showToast("Could not save consent. Please try again.");
  }
}


function _voiceStartRecording() {
  // Stop any existing recording first
  if (_voiceMediaRecorder && _voiceMediaRecorder.state !== "inactive") {
    _voiceMediaRecorder.stop();
  }
  clearInterval(_voiceRecordingTimer);
  _voiceAudioChunks   = [];
  _voiceAudioBlob     = null;
  _voiceRecordingSeconds = 0;

  const recordBtn    = el("voice-record-btn");
  const timerEl      = el("voice-record-timer");
  const previewSec   = el("voice-preview-section");
  const errorEl      = el("voice-setup-error");

  if (previewSec)  previewSec.style.display  = "none";
  if (errorEl)     errorEl.style.display     = "none";

  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      _voiceMediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

      _voiceMediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) _voiceAudioChunks.push(e.data);
      };

      _voiceMediaRecorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        clearInterval(_voiceRecordingTimer);
        _voiceAudioBlob = new Blob(_voiceAudioChunks, { type: "audio/webm" });

        // Show preview
        const player = el("voice-preview-player");
        if (player) {
          player.src = URL.createObjectURL(_voiceAudioBlob);
        }
        if (previewSec) previewSec.style.display = "block";
        if (recordBtn) {
          recordBtn.textContent = "● Start Recording";
          recordBtn.onclick     = _voiceStartRecording;
          recordBtn.style.background = "var(--gold)";
        }
        if (timerEl) timerEl.style.display = "none";
      };

      _voiceMediaRecorder.start(1000); // collect chunks every 1s

      // Update button to Stop
      if (recordBtn) {
        recordBtn.textContent  = "■ Stop Recording";
        recordBtn.onclick      = _voiceStopRecording;
        recordBtn.style.background = "var(--red,#c0392b)";
      }
      if (timerEl) timerEl.style.display = "inline";

      // Start timer
      _voiceRecordingTimer = setInterval(() => {
        _voiceRecordingSeconds++;
        const m = Math.floor(_voiceRecordingSeconds / 60);
        const s = String(_voiceRecordingSeconds % 60).padStart(2, "0");
        if (timerEl) timerEl.textContent = `${m}:${s}`;
      }, 1000);
    })
    .catch(err => {
      console.error("[Voice] Microphone access denied:", err);
      const errEl = el("voice-setup-error");
      if (errEl) {
        errEl.textContent = "Microphone access was denied. Please allow microphone access in your browser settings and try again.";
        errEl.style.display = "block";
      }
    });
}


function _voiceStopRecording() {
  if (_voiceMediaRecorder && _voiceMediaRecorder.state !== "inactive") {
    _voiceMediaRecorder.stop();
  }
}


function _voiceHandleFileUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const errorEl   = el("voice-setup-error");
  const previewSec = el("voice-preview-section");
  const player     = el("voice-preview-player");

  if (errorEl) errorEl.style.display = "none";

  _voiceAudioBlob = file;

  if (player) player.src = URL.createObjectURL(file);
  if (previewSec) previewSec.style.display = "block";
}


async function _voiceSubmitRecording() {
  if (!_voiceAudioBlob) {
    showToast("No recording to submit. Please record or upload a voice sample first.");
    return;
  }

  const submitBtn = el("voice-submit-btn");
  const errorEl   = el("voice-setup-error");

  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Saving…"; }
  if (errorEl)   errorEl.style.display = "none";

  try {
    const formData = new FormData();
    // Use .mp3 extension — LMNT accepts webm but .mp3 is safe for file upload compatibility
    const filename = _voiceAudioBlob instanceof File
      ? _voiceAudioBlob.name
      : "voice_sample.webm";
    formData.append("audio", _voiceAudioBlob, filename);

    // Use raw fetch — authFetch forces Content-Type: application/json which breaks FormData.
    // Set Authorization manually. Browser sets correct multipart/form-data with boundary.
    const token = localStorage.getItem("hb_token");
    const res = await fetch(`${BACKEND_URL}/voice/setup`, {
      method:  "POST",
      body:    formData,
      headers: token ? { "Authorization": `Bearer ${token}` } : {},
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Voice setup failed.");
    }

    // Success — reload the section to state 3
    showToast("Your voice is set up.");
    await _voiceLoadStatus();

  } catch(e) {
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Save My Voice"; }
    const msg = e.message || "Voice setup failed. Please try again.";
    if (errorEl) {
      errorEl.textContent = msg;
      errorEl.style.display = "block";
    } else {
      showToast(msg);
    }
  }
}


async function _voiceDelete(btnEl) {
  if (!confirm("Remove your voice? Your videos will use a default voice until you set up a new one.")) return;

  if (btnEl) { btnEl.disabled = true; btnEl.textContent = "Removing…"; }

  try {
    const res = await authFetch(`${BACKEND_URL}/voice/setup`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    showToast("Your voice has been removed.");
    await _voiceLoadStatus();
  } catch(e) {
    if (btnEl) { btnEl.disabled = false; btnEl.textContent = "Remove my voice"; }
    showToast("Could not remove voice. Please try again.");
  }
}

// ── END VOICE IDENTITY ────────────────────────────────────────────────────────


// Render a simple niche chip selector for idea/pulse/intel modes
// Uses selectedPrimaryNiches — clicking a chip sets ceSelectedNiche
let ceSelectedNiche = null;
function ceRenderNicheChips(containerId) {
  const container = el(containerId); if (!container) return;
  const saved  = getSaved();
  const niches = Array.isArray(saved.primaryNiches) ? saved.primaryNiches : [];
  if (!niches.length) {
    container.innerHTML = '<span style="font-size:13px;color:var(--ink-3);font-style:italic;">No niches saved — go to My Focus to add them.</span>';
    return;
  }
  // Default to first niche
  if (!ceSelectedNiche || !niches.includes(ceSelectedNiche)) ceSelectedNiche = niches[0];
  container.innerHTML = niches.map(n =>
    `<div class="chip${ceSelectedNiche===n?" selected":""}" onclick="ceSetNiche('${n.replace(/'/g,"\\'")}','${containerId}')">${n}</div>`
  ).join("");
}
function ceSetNiche(niche, containerId) {
  ceSelectedNiche = niche;
  ceRenderNicheChips(containerId);
}

function renderTrendsDisplay() {
  const container = el("content-engine-trends-display"); if (!container) return;
  const saved  = getSaved();
  const trends = Array.isArray(saved.trends) ? saved.trends.filter(t => t && typeof t === "string" && t.length > 0) : [];
  if (!trends.length) { container.innerHTML = '<span class="empty-text">None saved yet.</span>'; return; }
  container.innerHTML = trends.map(t => `<span class="chip selected" style="margin:2px;">${t}</span>`).join("");
}

// Build the shared agentProfile payload from saved setup
function ceAgentProfilePayload() {
  const saved  = getSaved();
  const hbUser = JSON.parse(localStorage.getItem("hb_user") || "null");
  return {
    agentName:           saved.agentName || hbUser?.agent_name || "",
    businessName:        saved.businessName || "",
    brokerage:           saved.brokerage || hbUser?.brokerage || "",
    market:              getMarketContext(),
    brandVoice:          saved.brandVoice || "",
    shortBio:            saved.shortBio || "",
    audienceDescription: saved.audienceDescription || "",
    wordsAvoid:          saved.wordsAvoid || "",
    wordsPrefer:         saved.wordsPrefer || "",
    mlsNames:            JSON.parse(localStorage.getItem("hb_mls") || "[]"),
    serviceAreas:        getServiceAreas(),
    designations:        getDesignations(),
    languagePref:        getLanguagePref(),
    state:               saved.state || "",
    ctaType:             saved.ctaType || "",
    ctaUrl:              saved.ctaUrl || "",
    ctaLabel:            saved.ctaLabel || "",
    originStory:         saved.originStory || "",
    unfairAdvantage:     saved.unfairAdvantage || "",
    signaturePerspective:saved.signaturePerspective || "",
    notForClient:        saved.notForClient || "",
    mlsData:             "",
    recruitingEnabled:   saved.recruitingEnabled || false,
    recruitingCta:       saved.recruitingCta || "",
  };
}

// Shared post-generation handler — saves to library, opens review modal
async function ceHandleResult(data, niche) {
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";

  // Guard: detect a broken generation before saving anything to the library.
  // A broken response has a missing, very short, or error-string headline.
  const headline = (data.headline || "").trim();
  const post     = (data.post     || "").trim();
  const isBroken = !headline || headline.length < 8 ||
    /error|failed|try again|could not|generation failed/i.test(headline) ||
    !post || post.length < 20;

  if (isBroken) {
    // Show error in the content engine panel — do NOT save to library, do NOT open modal
    showToast("⚠ Generation didn't return valid content — please try again.");
    return;
  }

  const contentPayload = {
    headline:      headline,
    thumbnailIdea: data.thumbnailIdea || "",
    hashtags:      data.hashtags      || "",
    post:          post,
    cta:           data.cta           || "",
    script:        data.script        || "",
  };
  if (isDemo) {
    const demoItem = { id:"demo-"+Date.now(), niche, content:contentPayload, compliance:data.compliance||null, status:"pending", created_at:new Date().toISOString(), is_demo:true };
    if (!window._demoLibrary) window._demoLibrary = [];
    window._demoLibrary.unshift(demoItem);
    navigateTo("library-panel"); openReviewModal(demoItem);
  } else {
    const libraryItem = await apiSaveLibraryItem(niche, contentPayload, data.compliance||null);
    navigateTo("library-panel"); openReviewModal(libraryItem);
  }
}

// ── MODE 2: My own idea ──
el("idea-generate-btn")?.addEventListener("click", async () => {
  const idea  = el("idea-input")?.value.trim() || "";
  const niche = ceSelectedNiche || (getSaved().primaryNiches||[])[0] || "Residential Buying & Selling";
  if (!idea) { showMsg("idea-error","⚠ Please describe your idea first — even a sentence or two is enough.",true); return; }
  hideMsg("idea-error");
  const btn = el("idea-generate-btn"); const ind = el("idea-generating-indicator");
  btn.disabled = true; btn.textContent = "Shaping your idea…";
  if (ind) ind.style.display = "block";
  try {
    const saved = getSaved();
    // Build a situation string from the agent's seed idea
    const situation = `Agent's original idea: "${idea}"`;
    const payload = {
      identity:    { primaryCategories:[niche], subNichesByCategory:{}, trendPreferences:saved.trends||[] },
      agentProfile:{ ...ceAgentProfilePayload(), seedIdea: idea },
      situation,
      persona:null, tone:null, length:"medium",
      content_mode: "agent",
      generation_mode: "idea",
    };
    const res  = await authFetch(`${BACKEND_URL}/content/generate-content`, { method:"POST", body:JSON.stringify(payload) });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    await ceHandleResult(data, niche);
  } catch(err) {
    if (err.message !== "Session expired") showMsg("idea-error","⚠ Generation failed. Please check your connection and try again.",true);
  } finally {
    btn.disabled = false; btn.textContent = "✦ Shape My Idea Into a Post";
    if (ind) ind.style.display = "none";
  }
});

// ── MODE 3: Market pulse — PDF upload + text paste ──

// State for the PDF upload flow
let _pulseActiveTab    = "pdf";   // "pdf" | "text"
let _pulseSelectedFile = null;    // File object
let _pulseExtracted    = null;    // Extracted stats dict from backend
let _pulseReportId     = null;    // Saved report id (for re-use reference)

// Switch between PDF tab and text tab
function pulseSwitchTab(tab) {
  _pulseActiveTab = tab;
  el("pulse-tab-pdf")?.classList.toggle("pulse-tab-active", tab === "pdf");
  el("pulse-tab-text")?.classList.toggle("pulse-tab-active", tab === "text");
  if (el("pulse-pdf-section"))  el("pulse-pdf-section").style.display  = tab === "pdf"  ? "block" : "none";
  if (el("pulse-text-section")) el("pulse-text-section").style.display = tab === "text" ? "block" : "none";
  // Enable generate button for text tab immediately; PDF tab requires extraction first
  const btn = el("pulse-generate-btn");
  if (btn) btn.disabled = (tab === "pdf" && !_pulseExtracted);
}

// Load saved reports list into the pulse panel
async function ceLoadSavedReports() {
  const container = el("pulse-saved-reports");
  const listEl    = el("pulse-saved-reports-list");
  if (!container || !listEl) return;
  try {
    const res = await authFetch(`${BACKEND_URL}/market-reports`);
    if (!res.ok) return;
    const data = await res.json();
    const reports = data.reports || [];
    if (!reports.length) { container.style.display = "none"; return; }
    container.style.display = "block";
    listEl.innerHTML = reports.map(r => {
      const title  = r.reportMonth || r.reportArea || r.filename || "Market Report";
      const source = r.sourceLabel || "MLS";
      const date   = r.uploadedAt ? new Date(r.uploadedAt + "T12:00:00").toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}) : "";
      const hasData = r.extractedData && Object.keys(r.extractedData).length > 0;
      return `<div class="pulse-saved-row" onclick="pulseLoadSavedReport(${JSON.stringify(r).replace(/"/g,"&quot;")})">
        <div style="font-size:20px;flex-shrink:0;">📊</div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:13px;font-weight:600;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${title}</div>
          <div style="font-size:11px;color:var(--ink-3);margin-top:1px;">${source} · ${date}</div>
        </div>
        <div style="font-size:11px;color:${hasData ? 'var(--green)' : 'var(--ink-3)'};">${hasData ? '✓ Data ready' : 'No data'}</div>
      </div>`;
    }).join("");
  } catch(e) {
    container.style.display = "none";
  }
}

// Load a saved report and show its extracted data
function pulseLoadSavedReport(report) {
  _pulseReportId  = report.id;
  _pulseExtracted = report.extractedData || null;
  _pulseSelectedFile = null;
  // Highlight selected row
  document.querySelectorAll(".pulse-saved-row").forEach(r => r.classList.remove("selected"));
  event.currentTarget?.classList.add("selected");
  if (_pulseExtracted) {
    pulseShowExtracted(_pulseExtracted, report.filename || "Saved Report");
  } else {
    showMsg("pulse-error","⚠ This report has no extracted data. Please upload the PDF again to re-extract.",true);
  }
}

// Handle file selection from the file input or drag-drop
function pulseHandleFileSelect(input) {
  const file = input.files?.[0];
  if (!file) return;
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    showMsg("pulse-error","⚠ Please select a PDF file.",true); return;
  }
  _pulseSelectedFile = file;
  _pulseExtracted    = null;
  _pulseReportId     = null;
  // Show file metadata row
  if (el("pulse-file-name")) el("pulse-file-name").textContent = file.name;
  if (el("pulse-file-size")) el("pulse-file-size").textContent = (file.size / 1024).toFixed(0) + " KB";
  if (el("pulse-file-meta"))  el("pulse-file-meta").style.display = "block";
  if (el("pulse-drop-zone"))  el("pulse-drop-zone").style.display = "none";
  if (el("pulse-upload-btn-row")) el("pulse-upload-btn-row").style.display = "block";
  if (el("pulse-extracted-card")) el("pulse-extracted-card").style.display = "none";
  const btn = el("pulse-generate-btn");
  if (btn) btn.disabled = true;
  hideMsg("pulse-error");
}

// Reset the PDF upload state — go back to drop zone
function pulseResetFile() {
  _pulseSelectedFile = null;
  _pulseExtracted    = null;
  _pulseReportId     = null;
  const inp = el("pulse-pdf-input"); if (inp) inp.value = "";
  if (el("pulse-file-meta"))      el("pulse-file-meta").style.display    = "none";
  if (el("pulse-drop-zone"))      el("pulse-drop-zone").style.display    = "block";
  if (el("pulse-upload-btn-row")) el("pulse-upload-btn-row").style.display = "none";
  if (el("pulse-extracted-card")) el("pulse-extracted-card").style.display = "none";
  if (el("pulse-extracting"))     el("pulse-extracting").style.display   = "none";
  const btn = el("pulse-generate-btn");
  if (btn) btn.disabled = true;
  hideMsg("pulse-error");
}

// Show the extracted stats preview card
function pulseShowExtracted(data, filename) {
  const card     = el("pulse-extracted-card");
  const titleEl  = el("pulse-extracted-title");
  const statsEl  = el("pulse-extracted-stats");
  const tkwyEl   = el("pulse-extracted-takeaway");
  if (!card || !titleEl || !statsEl) return;

  // Build title line
  const parts = [data.report_period, data.geographic_area].filter(Boolean);
  titleEl.textContent = parts.length ? parts.join(" · ") : (filename || "Market Report");

  // Key stat fields to display — label → data key
  const statFields = [
    ["Median Sale Price",     "median_sale_price",         "median_price_change"],
    ["Days on Market",        "days_on_market",             "days_on_market_change"],
    ["Active Listings",       "active_listings",            null],
    ["Months of Supply",      "months_of_supply",           "months_of_supply_change"],
    ["Closed Sales",          "closed_sales",               null],
    ["List-to-Sale Ratio",    "list_price_to_sale_ratio",  null],
    ["New Listings",          "new_listings",               null],
    ["Price per Sq Ft",       "price_per_sq_ft",           null],
  ];
  const chips = statFields
    .filter(([,key]) => data[key])
    .map(([label, key, changeKey]) => {
      const change = changeKey && data[changeKey] ? `<div class="pulse-stat-change">${data[changeKey]}</div>` : "";
      return `<div class="pulse-stat-chip">
        <div class="pulse-stat-label">${label}</div>
        <div class="pulse-stat-value">${data[key]}</div>
        ${change}
      </div>`;
    });

  // Add notable stats as small text if present
  const notable = (data.notable_stats || []).filter(Boolean);
  const notableHTML = notable.length ? `<div style="grid-column:1/-1;font-size:12px;color:var(--ink-3);line-height:1.7;padding-top:4px;">${notable.slice(0,3).join(" · ")}</div>` : "";

  statsEl.innerHTML = chips.join("") + notableHTML;

  // Takeaway
  if (tkwyEl) {
    tkwyEl.textContent = data.key_takeaway || "Report data extracted. Ready to generate a post.";
    tkwyEl.style.display = data.key_takeaway ? "block" : "none";
  }

  card.style.display = "block";
  if (el("pulse-generate-btn")) el("pulse-generate-btn").disabled = false;
  if (el("pulse-upload-btn-row")) el("pulse-upload-btn-row").style.display = "none";
}

// Extract data from the selected PDF
el("pulse-extract-btn")?.addEventListener("click", async () => {
  if (!_pulseSelectedFile) return;
  const btn     = el("pulse-extract-btn");
  const loading = el("pulse-extracting");
  btn.disabled = true; btn.textContent = "Reading report…";
  if (loading) loading.style.display = "block";
  hideMsg("pulse-error");

  try {
    // Read file as base64
    const b64 = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload  = e => resolve(e.target.result.split(",")[1]);
      reader.onerror = () => reject(new Error("Could not read file."));
      reader.readAsDataURL(_pulseSelectedFile);
    });

    const payload = {
      filename:     _pulseSelectedFile.name,
      pdf_data:     b64,
      source_label: el("pulse-source-label")?.value || "MLS",
      report_month: el("pulse-report-month")?.value.trim() || null,
      report_area:  getSaved().market || null,
    };

    const res = await authFetch(`${BACKEND_URL}/market-reports/upload`, {
      method: "POST",
      body:   JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Status ${res.status}`);
    }
    const data = await res.json();
    _pulseReportId  = data.report?.id || null;
    _pulseExtracted = data.extracted  || null;

    if (!_pulseExtracted) {
      showMsg("pulse-error","⚠ Could not extract data from this PDF. Try the 'Paste Data Manually' tab instead.",true);
      return;
    }
    pulseShowExtracted(_pulseExtracted, _pulseSelectedFile.name);
    // Refresh saved reports list
    ceLoadSavedReports();

  } catch(err) {
    showMsg("pulse-error","⚠ Extraction failed: " + (err.message || "Unknown error. Please try again."),true);
  } finally {
    btn.disabled = false; btn.textContent = "📊 Extract Market Data";
    if (loading) loading.style.display = "none";
  }
});

// Drag and drop support for the drop zone
(function() {
  const zone = el("pulse-drop-zone");
  if (!zone) return;
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    const file = e.dataTransfer?.files?.[0];
    if (file) {
      const inp = el("pulse-pdf-input");
      const dt  = new DataTransfer();
      dt.items.add(file);
      if (inp) { inp.files = dt.files; pulseHandleFileSelect(inp); }
    }
  });
})();

// Generate button — handles both PDF (extracted data) and text paste modes
el("pulse-generate-btn")?.addEventListener("click", async () => {
  const niche = ceSelectedNiche || (getSaved().primaryNiches||[])[0] || "Residential Buying & Selling";
  const btn   = el("pulse-generate-btn");
  const ind   = el("pulse-generating-indicator");

  // Determine source of market data
  let mlsData = "";
  if (_pulseActiveTab === "pdf" && _pulseExtracted) {
    // Build a text summary from extracted JSON so the content engine can use it
    const d = _pulseExtracted;
    const lines = [];
    if (d.report_period)          lines.push(`Report period: ${d.report_period}`);
    if (d.geographic_area)        lines.push(`Area: ${d.geographic_area}`);
    if (d.source)                 lines.push(`Source: ${d.source}`);
    if (d.median_sale_price)      lines.push(`Median sale price: ${d.median_sale_price}${d.median_price_change ? " (" + d.median_price_change + ")" : ""}`);
    if (d.days_on_market)         lines.push(`Days on market: ${d.days_on_market}${d.days_on_market_change ? " (" + d.days_on_market_change + ")" : ""}`);
    if (d.active_listings)        lines.push(`Active listings: ${d.active_listings}`);
    if (d.months_of_supply)       lines.push(`Months of supply: ${d.months_of_supply}${d.months_of_supply_change ? " (" + d.months_of_supply_change + ")" : ""}`);
    if (d.closed_sales)           lines.push(`Closed sales: ${d.closed_sales}`);
    if (d.list_price_to_sale_ratio) lines.push(`List-to-sale ratio: ${d.list_price_to_sale_ratio}`);
    if (d.new_listings)           lines.push(`New listings: ${d.new_listings}`);
    if (d.price_per_sq_ft)        lines.push(`Price per sq ft: ${d.price_per_sq_ft}`);
    if (d.average_sale_price)     lines.push(`Average sale price: ${d.average_sale_price}`);
    if (d.cash_sales_pct)         lines.push(`Cash sales: ${d.cash_sales_pct}`);
    if (d.absorption_rate)        lines.push(`Absorption rate: ${d.absorption_rate}`);
    const notable = (d.notable_stats || []).filter(Boolean);
    if (notable.length)           lines.push(`Notable: ${notable.join("; ")}`);
    if (d.key_takeaway)           lines.push(`Key insight: ${d.key_takeaway}`);
    mlsData = lines.join("\n");
  } else {
    mlsData = el("mls-data-input")?.value.trim() || "";
  }

  if (!mlsData) {
    if (_pulseActiveTab === "pdf") {
      showMsg("pulse-error","⚠ Please upload and extract a report first, or switch to 'Paste Data Manually'.",true);
    } else {
      showMsg("pulse-error","⚠ Please paste your MLS data before generating.",true);
    }
    return;
  }
  hideMsg("pulse-error");

  btn.disabled = true; btn.textContent = "Building your market post…";
  if (ind) ind.style.display = "block";

  try {
    const payload = {
      identity:    { primaryCategories:[niche], subNichesByCategory:{}, trendPreferences:[] },
      agentProfile:{ ...ceAgentProfilePayload(), mlsData },
      situation:   "Market data update — share what the numbers mean for buyers and sellers right now",
      persona:null, tone:null, length:"medium",
      content_mode:    "agent",
      generation_mode: "pulse",
    };
    const res  = await authFetch(`${BACKEND_URL}/content/generate-content`, { method:"POST", body:JSON.stringify(payload) });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    await ceHandleResult(data, niche);
  } catch(err) {
    if (err.message !== "Session expired") showMsg("pulse-error","⚠ Generation failed. Please check your connection and try again.",true);
  } finally {
    btn.disabled = false; btn.textContent = "✦ Build My Market Post";
    if (ind) ind.style.display = "none";
  }
});

// ── MODE 4: Local intel ──
el("intel-generate-btn")?.addEventListener("click", async () => {
  const location = el("intel-location-input")?.value.trim() || "";
  const niche    = ceSelectedNiche || (getSaved().primaryNiches||[])[0] || "Residential Buying & Selling";
  if (!location) { showMsg("intel-error","⚠ Please enter an address, intersection, or development name.",true); return; }
  hideMsg("intel-error");
  const btn = el("intel-generate-btn"); const ind = el("intel-generating-indicator");
  btn.disabled = true; btn.textContent = "Researching your market…";
  if (ind) ind.style.display = "block";
  try {
    const payload = {
      location,
      niche,
      agentProfile: ceAgentProfilePayload(),
      market:       getMarketContext(),
    };
    const res  = await authFetch(`${BACKEND_URL}/content/local-intel`, { method:"POST", body:JSON.stringify(payload) });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    await ceHandleResult(data, niche);
  } catch(err) {
    if (err.message !== "Session expired") showMsg("intel-error","⚠ Research failed. Please check your connection and try again.",true);
  } finally {
    btn.disabled = false; btn.textContent = "✦ Research & Write This Story";
    if (ind) ind.style.display = "none";
  }
});

// Auto-select guided mode when content engine panel loads
// and restore mode if returning to the panel
function ceInit() {
  renderIdentitySummary();
  renderNicheSelector();
  renderTrendsDisplay();
  fetchAndRenderScore();
  const niche = activeNicheForGenerate || (getSaved().primaryNiches||[])[0] || null;
  populateSituationDropdown(niche);
  updatePersonaDropdown(niche);
  if (!_ceActiveMode) ceSelectMode("guided");
  else ceSelectMode(_ceActiveMode);
}


function getComplianceBadgeHTML(compliance) {
  if (!compliance) return "";
  const s = compliance.overall_verdict || compliance.overallStatus || "review";
  const map = { pass:"✓ Pro-Reviewed", review:"⚠ Needs Review", fail:"✗ Attention Required", compliant:"✓ Pro-Reviewed", attention:"✗ Attention Required" };
  const col = { pass:"var(--green)", review:"var(--amber)", fail:"var(--red)", compliant:"var(--green)", attention:"var(--red)" };
  const label = map[s] || "⚠ Needs Review";
  const color = col[s] || "var(--amber)";

  // Build notes display — filter out boilerplate reminders for passing content
  const notes = Array.isArray(compliance.notes) ? compliance.notes : [];
  const isPass = s === "pass" || s === "compliant";
  const actionNotes = notes.filter(n => {
    const lower = n.toLowerCase();
    return !lower.includes("state rules:") && !lower.includes("jurisdiction note:") && !lower.includes("mls reminder:");
  });
  const boilerNotes = notes.filter(n => {
    const lower = n.toLowerCase();
    return lower.includes("state rules:") || lower.includes("jurisdiction note:") || lower.includes("mls reminder:");
  });

  // Per-category status pills
  const cats = [
    { label:"Fair Housing",        val: compliance.fairHousing        || compliance.fair_housing        || "pass" },
    { label:"Brokerage Disclosure",val: compliance.brokerageDisclosure || compliance.brokerage_disclosure|| "pass" },
    { label:"NAR Standards",       val: compliance.narStandards        || compliance.nar_standards       || "pass" },
  ];
  const catCol = { pass:"var(--green)", warn:"var(--amber)", fail:"var(--red)" };
  const catIcon = { pass:"✓", warn:"⚠", fail:"✗" };

  const catHTML = cats.map(c => {
    const v = c.val === "pass" ? "pass" : c.val === "fail" ? "fail" : "warn";
    return `<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:${v==="pass"?"rgba(21,128,61,0.08)":v==="fail"?"rgba(185,28,28,0.08)":"rgba(180,83,9,0.08)"};color:${catCol[v]};font-weight:600;">${catIcon[v]} ${c.label}</span>`;
  }).join("");

  // Action notes (actual violations/warnings)
  const notesHTML = actionNotes.length ? `
    <div style="margin-top:14px;display:flex;flex-direction:column;gap:8px;">
      ${actionNotes.map(n => {
        // Parse [Authority] Message format
        const match = n.match(/^\[([^\]]+)\]\s*(.+)$/);
        const authority = match ? match[1] : "";
        const message   = match ? match[2] : n;
        // Extract triggered term if present
        const trigMatch = message.match(/\(triggered:\s*'([^']+)'\)/);
        const triggered = trigMatch ? trigMatch[1] : null;
        const cleanMsg  = message.replace(/\s*\(triggered:\s*'[^']+'\)/, "").trim();
        return `<div style="padding:12px 14px;background:rgba(180,83,9,0.06);border-left:3px solid var(--amber);border-radius:0 6px 6px 0;">
          ${authority ? `<div style="font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:var(--amber);margin-bottom:4px;">${authority}</div>` : ""}
          <div style="font-size:13px;color:var(--ink-2);line-height:1.5;">${cleanMsg}</div>
          ${triggered ? `<div style="font-size:11px;color:var(--ink-3);margin-top:4px;">Triggered by: <code style="background:var(--bg);padding:1px 5px;border-radius:3px;font-family:monospace;">"${triggered}"</code></div>` : ""}
          <div style="margin-top:8px;padding:8px 10px;background:rgba(23,73,201,0.04);border-radius:5px;font-size:12px;color:var(--blue);line-height:1.5;">
            <strong style="font-size:10px;letter-spacing:0.06em;text-transform:uppercase;">Suggested fix:</strong><br>
            ${_getComplianceFix(authority, triggered, cleanMsg)}
          </div>
          ${triggered ? `<button data-triggered="${(triggered||'').replace(/"/g,'&quot;')}" data-suggestion="${(_getComplianceFix(authority,triggered,cleanMsg)||'').replace(/"/g,'&quot;')}" onclick="_applyFixFromBtn(this)" style="margin-top:8px;font-size:11px;font-weight:600;padding:5px 12px;background:var(--blue);color:#fff;border:none;border-radius:6px;cursor:pointer;font-family:inherit;">↩ Apply Fix in Editor</button>` : ""}
        </div>`;
      }).join("")}
    </div>` : "";

  // Boilerplate reminders — collapsed, subtle
  const boilerHTML = boilerNotes.length && !isPass ? `
    <details style="margin-top:10px;">
      <summary style="font-size:11px;color:var(--ink-3);cursor:pointer;list-style:none;">Show jurisdiction notes ▾</summary>
      <div style="margin-top:8px;padding:10px 12px;background:var(--bg);border-radius:6px;">
        ${boilerNotes.map(n => `<div style="font-size:12px;color:var(--ink-3);line-height:1.5;margin-bottom:6px;">${n}</div>`).join("")}
      </div>
    </details>` : "";

  return `
    <div style="margin-bottom:4px;">
      <span style="font-size:13px;font-weight:700;color:${color};">${label}</span>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">${catHTML}</div>
    ${notesHTML}
    ${boilerHTML}
  `;
}
// Open workspace with a compliance fix context — highlights the triggered term and shows the suggestion
function _applyFixFromBtn(btn) {
  const triggered  = btn.dataset.triggered  || "";
  const suggestion = btn.dataset.suggestion || "";
  _openWorkspaceWithFix(triggered, suggestion);
}
async function _openWorkspaceWithFix(triggered, suggestion) {
  if (!reviewModalItemId) return;
  const lib  = await fetchLibrary();
  const item = lib.find(x => String(x.id) === String(reviewModalItemId));
  if (!item) return;
  // Store fix context so workspace can display it
  window._pendingComplianceFix = { triggered, suggestion, itemId: reviewModalItemId };
  closeReviewModal();
  loadIntoWorkspace(item);
  navigateTo("workspace-panel");
  // Show fix banner after workspace renders
  setTimeout(() => _renderWorkspaceFixBanner(), 50);
}

function _renderWorkspaceFixBanner() {
  const fix = window._pendingComplianceFix;
  if (!fix) return;
  const result = el("ws-compliance-result");
  if (!result) return;
  result.style.display = "block";
  result.innerHTML = `
    <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--amber);margin-bottom:6px;">⚠ Compliance Fix Needed</div>
    <div style="font-size:13px;color:var(--ink-2);margin-bottom:6px;">Find and fix: <code style="background:var(--bg);padding:2px 6px;border-radius:4px;font-family:monospace;color:var(--red);">"${fix.triggered}"</code></div>
    <div style="font-size:12px;color:var(--ink-3);line-height:1.6;">${fix.suggestion}</div>
  `;
  // Highlight the triggered term in the post field
  const postEl = el("ws-post");
  if (postEl && fix.triggered) {
    const html = postEl.innerHTML;
    const highlighted = html.replace(
      new RegExp(`(${fix.triggered.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'),
      '<mark style="background:#fef3c7;color:#92400e;border-radius:2px;padding:0 2px;">$1</mark>'
    );
    if (highlighted !== html) postEl.innerHTML = highlighted;
  }
}

// Generate a plain-English fix suggestion from compliance warning context
function _getComplianceFix(authority, triggered, message) {
  const auth = (authority || "").toLowerCase();
  const trig = (triggered || "").toLowerCase();
  const msg  = (message  || "").toLowerCase();

  // Name/disclosure not found
  if (msg.includes("licensee disclosure") || msg.includes("not detected")) {
    return "Add your name and brokerage to the sign-off at the end of the post. Example: — Your Name | Your Brokerage · Equal Housing Opportunity";
  }
  if (msg.includes("company disclosure")) {
    return "Add your company name to the post footer. It should appear naturally in the sign-off line.";
  }

  // Fair Housing
  if (auth.includes("fair housing")) {
    if (trig.includes("school district")) return `Remove "${triggered}" — instead describe the home's features or proximity to amenities without referencing schools.`;
    if (trig.includes("master")) return `Replace "${triggered}" with "primary bedroom" or "owner's suite."`;
    if (trig.includes("safe") || trig.includes("quiet")) return `Remove "${triggered}" — describe the property itself, not neighborhood character. Use specific facts instead.`;
    if (trig.includes("families") || trig.includes("couples") || trig.includes("professionals")) return `Remove "${triggered}" — describe who the property works for in terms of features and lifestyle, not demographics.`;
    return `Remove or rephrase "${triggered}" — use property-specific language rather than neighborhood or demographic characterizations.`;
  }

  // NAR Article 12 — unverifiable claims
  if (auth.includes("nar") || auth.includes("article 12")) {
    if (trig.includes("guaranteed") || trig.includes("guarantee")) return `Replace "${triggered}" with qualified language. Example: "In my experience" or "clients have found" or "historically" rather than making a guarantee.`;
    if (trig.includes("best") || trig.includes("number one") || trig.includes("#1")) return `Remove "${triggered}" — superlatives must be verifiable. Use specific, factual claims instead: "I've closed X transactions in this market" is stronger and defensible.`;
    if (trig.includes("will sell") || trig.includes("promise")) return `Replace "${triggered}" with "my goal is to" or "I work to" — agents cannot guarantee outcomes.`;
    return `Rephrase to remove the unverifiable claim. Add qualifying language: "in my experience," "typically," or "my approach is to" rather than stating outcomes as certain.`;
  }

  // RESPA
  if (auth.includes("respa")) {
    return `Remove "${triggered}" — any language implying compensation for referrals must be removed. Describe the service you provide without referencing fee arrangements.`;
  }

  // FTC
  if (auth.includes("ftc")) {
    if (trig) return `Remove or qualify "${triggered}" — performance claims must be substantiated. Add "results may vary" or use specific verifiable data instead of absolute claims.`;
    return "Add qualifying language to performance claims. Avoid absolute statements — use 'in our experience' or cite specific verifiable data.";
  }

  // SEC
  if (auth.includes("sec")) {
    return `Remove "${triggered}" — investment return projections or guarantees require securities disclosure. Reframe as: "historically this type of asset has" or "investors in this market have seen" with appropriate caveats.`;
  }

  // Default
  if (triggered) return `Remove or rephrase "${triggered}" to address this compliance concern before approving.`;
  return "Review and rephrase the flagged content before approving. Click Edit to make changes directly.";
}

function complianceIcon(c) {
  if (!c) return '<span style="color:var(--ink-4);font-size:11px;" title="Not yet reviewed">—</span>';
  const s = c.overall_verdict || c.overallStatus || "";
  // Map all engine status values — "reviewed" and "pass" are the normal success states
  const greenStates = ["pass","reviewed","compliant"];
  const amberStates = ["warn","review-recommended","review_recommended"];
  const redStates   = ["fail","attention-required","attention_required"];
  if (greenStates.includes(s)) return '<span style="font-weight:700;color:var(--green);" title="Pre-publication review completed">✓</span>';
  if (amberStates.includes(s)) return '<span style="font-weight:700;color:var(--amber);" title="Review note — tap to see details">!</span>';
  if (redStates.includes(s))   return '<span style="font-weight:700;color:var(--red);" title="Attention required — tap to see details">✗</span>';
  // Any non-empty status that isn't a failure = reviewed
  if (s) return '<span style="font-weight:700;color:var(--green);" title="Pre-publication review completed">✓</span>';
  return '<span style="color:var(--ink-4);font-size:11px;" title="Not yet reviewed">—</span>';
}

async function renderLibrary() {
  const index = el("library-index"); if (!index) return;
  index.innerHTML = '<div style="padding:24px;text-align:center;color:var(--ink-4);font-size:13px;">Loading…</div>';
  // Always force refresh when viewing archived — never serve cached for archived tab
  const isArchived = currentLibraryFilter === "archived";
  if (isArchived) _cachedLibrary = null;
  let library;
  try { library = await fetchLibrary(true); }
  catch(err) { index.innerHTML = '<div style="padding:24px;text-align:center;color:var(--muted);">Could not load Records. Check your connection.</div>'; return; }

  // Filter by status
  if (isArchived) {
    library = library.filter(x => x.status === "archived");
  } else if (currentLibraryFilter !== "all") {
    library = library.filter(x => (x.status||"pending") === currentLibraryFilter);
  } else {
    // "All" tab — always exclude archived items
    library = library.filter(x => x.status !== "archived");
  }

  // Clear selection on re-render
  libSelectedIds.clear();
  libUpdateBulkBar();

  if (!library.length) {
    index.innerHTML = isArchived
      ? '<div style="padding:48px 24px;text-align:center;color:var(--ink-4);font-size:13px;">No archived content. Move items here to keep your active Records clean.</div>'
      : '<div style="padding:48px 24px;text-align:center;color:var(--ink-4);font-size:13px;line-height:1.8;">All clear — nothing here.<br><span style="font-size:12px;">Generate content in Studio and it will appear here.</span></div>';
    return;
  }

  index.innerHTML = `<div class="library-index-header">
    <span><input type="checkbox" class="lib-cb" id="lib-cb-all" title="Select all" onclick="libToggleAll(this)" /></span>
    <span>Date</span><span>Headline</span><span>Niche</span><span>Status</span><span>Review</span>
  </div>`
    + library.map(item => {
      const raw = item.savedAt||item.created_at||item.approvedAt||null;
      const d   = raw ? new Date(raw) : null;
      const date = (d && !isNaN(d)) ? d.toLocaleDateString("en-US",{month:"short",day:"numeric"}) : "Today";
      const status = item.status || "pending";
      const statusLabel = status==="published"?"Published":status==="approved"?"Approved":status==="archived"?"Archived":"⏳ Awaiting Review";
      const headline = (item.content?.headline||"Untitled").slice(0,80);
      const isSelected = libSelectedIds.has(String(item.id));

      // Action buttons — context sensitive
      const quickApprove  = status==="pending"  ? `<span data-quick-approve="${item.id}" style="margin-left:8px;font-size:11px;font-weight:600;color:var(--green);background:var(--green-dim,rgba(26,127,75,0.08));border:1px solid rgba(15,110,59,0.2);border-radius:4px;padding:2px 10px;cursor:pointer;">Approve</span>` : "";
      const sendApproval  = status==="pending"  ? `<span data-send-approval="${item.id}" style="margin-left:6px;font-size:11px;font-weight:600;color:var(--blue);background:var(--blue-dim,rgba(23,73,201,0.07));border:1px solid rgba(23,73,201,0.18);border-radius:4px;padding:2px 10px;cursor:pointer;">Resend to My Phone</span>` : "";
      const quickDistrib  = status==="approved" ? `<span data-quick-dist="${item.id}" style="margin-left:8px;font-size:11px;font-weight:600;color:var(--blue);background:var(--blue-dim,rgba(23,73,201,0.08));border:1px solid rgba(23,73,201,0.2);border-radius:4px;padding:2px 10px;cursor:pointer;" onclick="event.stopPropagation();(async()=>{const lib=await fetchLibrary();const it=lib.find(x=>String(x.id)==='${item.id}');if(it)openDistribution(it.content,it.niche,it.id);})();">Publish →</span>` : "";

      // Archive button — shown on all non-archived items
      const archiveBtn = status !== "archived" ? `<span data-archive-item="${item.id}" style="margin-left:6px;font-size:11px;font-weight:600;color:var(--ink-3);background:var(--bg-sunken,#f5f5f3);border:1px solid var(--border);border-radius:4px;padding:2px 10px;cursor:pointer;" title="Move to Archive">Archive</span>` : "";

      // Restore + Delete — shown only in archived view
      const restoreBtn = status === "archived" ? `<span data-restore-item="${item.id}" style="margin-left:6px;font-size:11px;font-weight:600;color:var(--blue);background:var(--blue-dim);border:1px solid var(--blue-border);border-radius:4px;padding:2px 10px;cursor:pointer;">Restore</span>` : "";
      const deleteBtn  = status === "archived" ? `<span data-delete-item="${item.id}" style="margin-left:6px;font-size:11px;font-weight:600;color:#b91c1c;background:#fff7f7;border:1px solid rgba(185,28,28,0.2);border-radius:4px;padding:2px 10px;cursor:pointer;">Delete</span>` : "";

      return `<div class="library-index-row${isSelected?" lib-selected":""}" data-row-id="${item.id}">
        <span onclick="event.stopPropagation()"><input type="checkbox" class="lib-cb lib-row-cb" data-cb-id="${item.id}" ${isSelected?"checked":""} onclick="libToggleRow(this)" /></span>
        <span>${date}</span>
        <span style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">${headline}${quickApprove}${sendApproval}${quickDistrib}${archiveBtn}${restoreBtn}${deleteBtn}</span>
        <span>${(item.niche||"").slice(0,20)}</span>
        <span><span class="lib-status-pill lib-status-${status}">${statusLabel}</span></span>
        <span>${complianceIcon(item.compliance)}</span>
      </div>`;
    }).join("");

  index.querySelectorAll(".library-index-row").forEach(row => {
    row.addEventListener("click", async e => {
      // Quick approve
      if (e.target.dataset.quickApprove) {
        await apiPatchLibraryItem(e.target.dataset.quickApprove, { status:"approved", approvedAt:new Date().toISOString() });
        gsMarkDone(3); _cachedLibrary = null; renderLibrary(); fetchAndRenderScore(); return;
      }
      // Resend approval
      if (e.target.dataset.sendApproval) {
        const itemId = e.target.dataset.sendApproval;
        e.target.textContent = "Sending…"; e.target.style.opacity = ".6"; e.target.style.pointerEvents = "none";
        try {
          const res  = await authFetch(`${BACKEND_URL}/library/${itemId}/send-approval`, { method:"POST" });
          const data = await res.json();
          showToast(data.email_sent || data.sms_sent ? "Approval link sent ✓" : "Token created — add email or phone in Profile to send notifications.");
        } catch(err) { showToast("Could not send approval link. Try again."); }
        finally { e.target.textContent = "Resend to My Phone"; e.target.style.opacity = ""; e.target.style.pointerEvents = ""; }
        return;
      }
      // Archive
      if (e.target.dataset.archiveItem) {
        await apiPatchLibraryItem(e.target.dataset.archiveItem, { status:"archived" });
        _cachedLibrary = null; renderLibrary();
        showToast("Moved to Archive. Your CIR™ compliance record is preserved.");
        return;
      }
      // Restore from archive
      if (e.target.dataset.restoreItem) {
        await apiPatchLibraryItem(e.target.dataset.restoreItem, { status:"approved" });
        _cachedLibrary = null; renderLibrary();
        showToast("Restored to Approved.");
        return;
      }
      // Delete — two-step confirmation
      if (e.target.dataset.deleteItem) {
        e.stopPropagation();
        showDeleteConfirmation(e.target.dataset.deleteItem);
        return;
      }
      // Open review modal
      if (!e.target.dataset.quickDist) {
        const library = await fetchLibrary();
        const item = library.find(x=>String(x.id)===String(row.dataset.rowId));
        if (item) openReviewModal(item);
      }
    });
  });
}

function showDeleteConfirmation(itemId) {
  // Remove any existing confirmation
  document.getElementById("lib-delete-confirm")?.remove();

  const overlay = document.createElement("div");
  overlay.id = "lib-delete-confirm";
  overlay.style.cssText = `
    position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;
    display:flex;align-items:center;justify-content:center;padding:24px;
  `;

  overlay.innerHTML = `
    <div style="background:#fff;border-radius:16px;padding:32px;max-width:440px;width:100%;box-shadow:0 24px 64px rgba(0,0,0,0.18);">
      <div style="font-size:32px;margin-bottom:16px;text-align:center;">⚠️</div>
      <div style="font-size:18px;font-weight:700;color:var(--ink);margin-bottom:10px;text-align:center;">Permanently Delete This Post?</div>
      <div style="font-size:14px;color:var(--ink-3);line-height:1.65;margin-bottom:8px;text-align:center;">
        This will permanently remove this post from your Library.
      </div>
      <div style="font-size:13px;color:var(--green,#15803d);background:var(--green-dim,#f0fdf4);border:1px solid rgba(21,128,61,0.2);border-radius:8px;padding:10px 14px;margin-bottom:24px;line-height:1.55;">
        ✓ Your CIR™ compliance record is preserved separately and is not affected by deletion.
      </div>
      <div style="display:flex;gap:10px;">
        <button id="lib-delete-cancel" style="flex:1;padding:12px;background:var(--bg-sunken,#f5f5f3);color:var(--ink);border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">
          Cancel
        </button>
        <button id="lib-delete-confirm-btn" style="flex:1;padding:12px;background:#b91c1c;color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">
          Yes, Delete Permanently
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  document.getElementById("lib-delete-cancel").addEventListener("click", () => overlay.remove());
  overlay.addEventListener("click", e => { if (e.target === overlay) overlay.remove(); });

  document.getElementById("lib-delete-confirm-btn").addEventListener("click", async () => {
    const btn = document.getElementById("lib-delete-confirm-btn");
    btn.textContent = "Deleting…"; btn.disabled = true;
    try {
      await apiDeleteLibraryItem(itemId);
      overlay.remove();
      _cachedLibrary = null;
      renderLibrary();
      showToast("Post permanently deleted.");
    } catch(e) {
      btn.textContent = "Yes, Delete Permanently"; btn.disabled = false;
      showToast("Delete failed — please try again.");
    }
  });
}

// ── Library bulk selection ────────────────────────────────────────────────────

function libToggleRow(cb) {
  const id = cb.dataset.cbId;
  if (cb.checked) libSelectedIds.add(id);
  else            libSelectedIds.delete(id);
  const row = cb.closest(".library-index-row");
  if (row) row.classList.toggle("lib-selected", cb.checked);
  libUpdateBulkBar();
  // Update select-all checkbox indeterminate state
  const allCb = el("lib-cb-all");
  if (allCb) {
    const total   = document.querySelectorAll(".lib-row-cb").length;
    const checked = libSelectedIds.size;
    allCb.checked       = checked === total && total > 0;
    allCb.indeterminate = checked > 0 && checked < total;
  }
}

function libToggleAll(masterCb) {
  document.querySelectorAll(".lib-row-cb").forEach(cb => {
    cb.checked = masterCb.checked;
    const id = cb.dataset.cbId;
    if (masterCb.checked) libSelectedIds.add(id);
    else                  libSelectedIds.delete(id);
    const row = cb.closest(".library-index-row");
    if (row) row.classList.toggle("lib-selected", masterCb.checked);
  });
  libUpdateBulkBar();
}

function libClearSelection() {
  libSelectedIds.clear();
  document.querySelectorAll(".lib-row-cb").forEach(cb => {
    cb.checked = false;
    cb.closest(".library-index-row")?.classList.remove("lib-selected");
  });
  const allCb = el("lib-cb-all");
  if (allCb) { allCb.checked = false; allCb.indeterminate = false; }
  libUpdateBulkBar();
}

function libUpdateBulkBar() {
  const bar   = el("lib-bulk-bar");
  const count = el("lib-bulk-count");
  if (!bar) return;
  const n = libSelectedIds.size;
  if (n > 0) {
    bar.classList.add("visible");
    if (count) count.textContent = `${n} item${n > 1 ? "s" : ""} selected`;
  } else {
    bar.classList.remove("visible");
  }
}

async function libBulkArchive() {
  const ids = [...libSelectedIds];
  if (!ids.length) return;
  const bar = el("lib-bulk-bar");
  if (bar) bar.style.opacity = "0.5";
  try {
    await Promise.all(ids.map(id => apiPatchLibraryItem(id, { status:"archived" })));
    _cachedLibrary = null;
    showToast(`${ids.length} item${ids.length > 1 ? "s" : ""} archived. CIR™ compliance record preserved.`);
  } catch(e) {
    showToast("Archive failed — please try again.");
  } finally {
    if (bar) bar.style.opacity = "";
    renderLibrary();
  }
}

async function libBulkDelete() {
  const ids = [...libSelectedIds];
  if (!ids.length) return;

  // Confirmation modal
  const existing = document.getElementById("lib-delete-confirm");
  if (existing) existing.remove();
  const overlay = document.createElement("div");
  overlay.id = "lib-delete-confirm";
  overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px;";
  overlay.innerHTML = `
    <div style="background:#fff;border-radius:16px;padding:32px;max-width:440px;width:100%;box-shadow:0 24px 64px rgba(0,0,0,0.18);">
      <div style="font-size:32px;margin-bottom:16px;text-align:center;">⚠️</div>
      <div style="font-size:18px;font-weight:700;color:var(--ink);margin-bottom:10px;text-align:center;">Delete ${ids.length} item${ids.length > 1 ? "s" : ""} permanently?</div>
      <div style="font-size:14px;color:var(--ink-3);line-height:1.65;margin-bottom:8px;text-align:center;">This cannot be undone.</div>
      <div style="font-size:13px;color:var(--green,#15803d);background:var(--green-dim,#f0fdf4);border:1px solid rgba(21,128,61,0.2);border-radius:8px;padding:10px 14px;margin-bottom:24px;line-height:1.55;">
        ✓ Your CIR™ compliance record is preserved separately and is not affected by deletion.
      </div>
      <div style="display:flex;gap:10px;">
        <button id="lib-bulk-delete-cancel" style="flex:1;padding:12px;background:var(--bg-sunken,#f5f5f3);color:var(--ink);border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Cancel</button>
        <button id="lib-bulk-delete-confirm" style="flex:1;padding:12px;background:#b91c1c;color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;">Delete ${ids.length} item${ids.length > 1 ? "s" : ""}</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  document.getElementById("lib-bulk-delete-cancel").addEventListener("click", () => overlay.remove());
  overlay.addEventListener("click", e => { if (e.target === overlay) overlay.remove(); });
  document.getElementById("lib-bulk-delete-confirm").addEventListener("click", async () => {
    const btn = document.getElementById("lib-bulk-delete-confirm");
    btn.textContent = "Deleting…"; btn.disabled = true;
    try {
      await Promise.all(ids.map(id => apiDeleteLibraryItem(id)));
      overlay.remove();
      _cachedLibrary = null;
      showToast(`${ids.length} item${ids.length > 1 ? "s" : ""} permanently deleted.`);
    } catch(e) {
      btn.textContent = `Delete ${ids.length} item${ids.length > 1 ? "s" : ""}`;
      btn.disabled = false;
      showToast("Delete failed — please try again.");
    } finally {
      renderLibrary();
    }
  });
}
document.querySelectorAll(".lib-filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".lib-filter-btn").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    currentLibraryFilter = btn.dataset.filter || "all";
    libSelectedIds.clear();
    renderLibrary();
  });
});

// ─────────────────────────────────────────────
// SECTION 27: REVIEW MODAL
// ─────────────────────────────────────────────
// ─────────────────────────────────────────────
// REVIEW MODAL — helpers
// ─────────────────────────────────────────────

function _escHtml(s) {
  return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function _escRx(s) { return String(s||"").replace(/[.*+?^${}()|[\]\\]/g,"\\$&"); }

function _parseRmFlags(notes, content) {
  if (!Array.isArray(notes)) return [];
  const fields = {
    post:      (content.post         ||"").toLowerCase(),
    cta:       (content.cta          ||"").toLowerCase(),
    script:    (content.script       ||"").toLowerCase(),
    thumbnail: (content.thumbnailIdea||"").toLowerCase(),
    headline:  (content.headline     ||"").toLowerCase(),
  };
  return notes.reduce((acc, note) => {
    const lc = note.toLowerCase();
    if (/state rules:|jurisdiction note:|mls reminder:|ftc reminder:|automated checks cover/.test(lc)) return acc;
    const m = note.match(/^\[([^\]]+)\]\s*(.+)$/); if (!m) return acc;
    const authority = m[1], message = m[2];
    const tm = message.match(/\(triggered:\s*'([^']+)'\)/); if (!tm) return acc;
    const triggered    = tm[1];
    const cleanMessage = message.replace(/\s*\(triggered:\s*'[^']+'\)/,"").trim();
    const tl = triggered.toLowerCase();
    let location = "unknown";
    for (const [f,txt] of Object.entries(fields)) { if (txt.includes(tl)) { location=f; break; } }
    const publishable = ["post","cta","headline","unknown"].includes(location);
    acc.push({ authority, triggered, cleanMessage, location, publishable });
    return acc;
  }, []);
}

function _highlightRmFlags(text, flags, field) {
  if (!text) return "";
  const hits = flags.filter(f => f.location===field || (field==="post"&&f.location==="unknown"));
  if (!hits.length) return _escHtml(text);
  let r = _escHtml(text);
  [...hits].sort((a,b)=>b.triggered.length-a.triggered.length).forEach(flag => {
    const t   = _escHtml(flag.triggered);
    const fix = _escHtml(_getComplianceFix(flag.authority,flag.triggered,flag.cleanMessage)||"");
    const auth= _escHtml(flag.authority);
    const msg = _escHtml(flag.cleanMessage);
    r = r.replace(new RegExp(_escRx(t),"gi"),
      `<mark class="rm-flag" data-t="${t}" data-a="${auth}" data-fix="${fix}" data-msg="${msg}" `+
      `style="background:#fef3c7;color:#92400e;border-bottom:2px solid #f59e0b;border-radius:2px;padding:0 1px;cursor:pointer;">${t}</mark>`);
  });
  return r;
}

function _buildRmAccordion(label, bodyHtml, id, softNotes) {
  const notes = (softNotes||[]).map(f=>
    `<div style="margin-top:8px;padding:7px 10px;background:rgba(245,158,11,.08);border-left:3px solid #f59e0b;border-radius:0 6px 6px 0;font-size:12px;color:#92400e;line-height:1.5;">
      ⚠ <strong>"${_escHtml(f.triggered)}"</strong> — ${_escHtml(f.cleanMessage)}
      <span style="display:block;font-size:11px;color:var(--ink-3);margin-top:2px;">Script/thumbnail only — not published unless you film this.</span>
    </div>`).join("");
  return `<div style="border-top:1px solid var(--border);">
    <button class="rm-acc-toggle" data-target="${id}"
      style="width:100%;display:flex;align-items:center;justify-content:space-between;padding:13px 0;background:none;border:none;cursor:pointer;font-family:inherit;">
      <span style="font-size:12px;font-weight:600;color:var(--ink-2);">${label}</span>
      <span class="rm-acc-arrow" style="font-size:11px;color:var(--ink-4);transition:transform .2s;">▸</span>
    </button>
    <div id="${id}" style="display:none;padding-bottom:14px;">
      <div style="font-size:13px;color:var(--ink-2);line-height:1.75;white-space:pre-wrap;word-break:break-word;">${bodyHtml}</div>
      ${notes}
    </div>
  </div>`;
}

// ─────────────────────────────────────────────
// BROADCAST PANEL — world-class review & publish
// ─────────────────────────────────────────────

let _bcItem       = null;
let _bcImageUrl   = null;
let _bcActiveMark = null;
let _bcSelectedPlts = new Set();
let _bcAllFlags   = [];
// reviewModalItemId declared at top of file

const _bcPlatMeta = {
  linkedin:  { label:'LinkedIn',     icon:'LI', bg:'var(--blue-dim)',       fg:'var(--blue)'        },
  facebook:  { label:'Facebook',     icon:'FB', bg:'var(--blue-dim)',       fg:'var(--blue)'        },
  instagram: { label:'Instagram',    icon:'IG', bg:'rgba(217,119,6,.1)',    fg:'#d97706'            },
  youtube:   { label:'YouTube',      icon:'YT', bg:'rgba(185,28,28,.1)',    fg:'var(--red,#b91c1c)' },
  twitter:   { label:'X / Twitter', icon:'X',  bg:'rgba(0,0,0,.06)',       fg:'var(--ink)'         },
  tiktok:    { label:'TikTok',       icon:'TT', bg:'rgba(0,0,0,.06)',       fg:'var(--ink)'         },
  nextdoor:  { label:'Nextdoor',     icon:'ND', bg:'rgba(26,127,75,.1)',    fg:'var(--green)'       },
  reddit:    { label:'Reddit',       icon:'Re', bg:'rgba(185,28,28,.1)',    fg:'var(--red,#b91c1c)' },
  google:    { label:'Google Biz',   icon:'G',  bg:'rgba(26,127,75,.1)',    fg:'var(--green)'       },
};

function openReviewModal(item) {
  _bcItem = item;
  reviewModalItemId = item.id;
  _bcImageUrl = item.image_url || null;
  _bcAllFlags = [];
  _bcSelectedPlts = new Set();
  const panel = el('broadcast-panel'); if (!panel) return;
  panel.classList.add('open');
  panel.style.display = 'flex'; // clear inline display:none so CSS .open rule takes effect
  document.body.style.overflow = 'hidden';
  // Reset image button state — prevents stuck "⏳ Generating…" if prior session failed or timed out
  const _imgBtn = el('bc-gen-img'), _imgSt = el('bc-img-status');
  if (_imgBtn) { _imgBtn.disabled = false; _imgBtn.textContent = '🎨 Generate image'; }
  if (_imgSt) { _imgSt.style.display = 'none'; _imgSt.textContent = ''; }
  _bcShowScreen('review');
  _bcPopulateReview(item);
}

function closeReviewModal() {
  const panel = el('broadcast-panel'); if (!panel) return;
  panel.classList.remove('open');
  panel.style.display = 'none';
  setTimeout(() => { panel.style.display = ''; }, 50);
  document.body.style.overflow = '';
  _bcItem = null; _bcImageUrl = null; _bcActiveMark = null;
  _bcCloseFix();
}

function _bcShowScreen(name) {
  ['review','channels','broadcasting','live'].forEach(s => {
    const e = el('bc-screen-' + s); if (e) e.style.display = 'none';
  });
  const bar = el('bc-action-bar'); if (bar) bar.style.display = name === 'review' ? 'block' : 'none';
  const target = el('bc-screen-' + name); if (target) target.style.display = 'block';

  const labels = { review:'Review your story', channels:'Choose channels' };
  const stepEl = el('bc-step-label'); if (stepEl) stepEl.textContent = labels[name] || '';

  const backBtn = el('bc-back');
  if (backBtn) backBtn.style.display = name === 'channels' ? 'inline-block' : 'none';

  const dots = [el('bc-dot-1'), el('bc-dot-2'), el('bc-dot-3')];
  const dotMap = { review:0, channels:1, broadcasting:2, live:2 };
  dots.forEach((d, i) => { if (d) d.style.background = i <= (dotMap[name] ?? 0) ? 'var(--blue)' : 'var(--border)'; });
}

function _bcPopulateReview(item) {
  const con  = item.content   || {};
  const comp = item.compliance || {};
  const saved = getSaved();
  const user  = JSON.parse(localStorage.getItem('hb_user') || 'null');
  const isDemo = localStorage.getItem('hb_demo_mode') === 'true';

  const name     = (isDemo ? 'Brooke Callahan' : (saved.agentName || user?.agent_name || 'Agent'));
  const brok     = (isDemo ? 'eXp Realty' : (saved.brokerage || user?.brokerage || ''));
  const mkt      = (isDemo ? 'Austin, TX' : (saved.market || ''));
  const initials = getInitials(name);

  const avatarEl = el('bc-avatar'); if (avatarEl) avatarEl.textContent = initials;
  const nameEl   = el('bc-agent-name'); if (nameEl) nameEl.textContent = name;
  const subEl    = el('bc-agent-sub');
  if (subEl) subEl.textContent = [brok, mkt].filter(Boolean).join(' · ');

  const notes     = Array.isArray(comp.notes) ? comp.notes : [];
  _bcAllFlags     = _parseRmFlags(notes, con);
  const postFlags = _bcAllFlags.filter(f => f.publishable);
  const hasFlags  = postFlags.length > 0;

  const bar  = el('bc-compliance-bar');
  const dot  = el('bc-comp-dot');
  const txt  = el('bc-comp-text');
  const hint = el('bc-edit-hint');
  const verifiedEl = el('bc-comp-verified');
  if (bar) {
    bar.style.display = 'flex';

    // Build the verified-dates line from badge data (populated by compliance engine)
    let verifiedLine = '';
    if (comp.rules_verified_dates || comp.rules_version) {
      const dates = comp.rules_verified_dates || {};
      const version = comp.rules_version || '';
      const parts = [];
      if (dates.federal) parts.push('Federal rules: ' + dates.federal);
      // Show agent's state if present (any key that's 2 uppercase letters)
      const stateKey = Object.keys(dates).find(k => k !== 'federal' && k !== 'nar' && /^[A-Z]{2}$/.test(k));
      if (stateKey) parts.push(stateKey + ' rules: ' + dates[stateKey]);
      if (version) parts.push('v' + version);
      if (parts.length) verifiedLine = 'Rules verified: ' + parts.join(' · ');
    }

    if (hasFlags) {
      bar.style.cssText += 'background:#fffbeb;border:1px solid rgba(245,158,11,0.3);border-radius:10px;';
      if (dot) dot.style.background = '#f59e0b';
      if (txt) { txt.style.color = '#92400e'; txt.textContent = postFlags.length + ' compliance note' + (postFlags.length > 1 ? 's' : '') + ' — tap highlighted text to fix.'; }
      if (hint) hint.style.display = 'block';
      if (verifiedEl) { verifiedEl.style.display = verifiedLine ? 'block' : 'none'; verifiedEl.textContent = verifiedLine; }
    } else {
      bar.style.cssText += 'background:var(--green-dim);border:1px solid rgba(26,127,75,0.2);border-radius:10px;';
      if (dot) dot.style.background = 'var(--green)';
      if (txt) { txt.style.color = 'var(--green)'; txt.textContent = 'Pro-Reviewed — no issues detected.'; }
      if (hint) hint.style.display = 'none';
      if (verifiedEl) { verifiedEl.style.display = verifiedLine ? 'block' : 'none'; verifiedEl.textContent = verifiedLine; }
    }
  }

  const hl = el('bc-headline'); if (hl) hl.textContent = con.headline || '';
  const postEl = el('bc-post');
  if (postEl) postEl.innerHTML = _bcHighlightFlags(con.post || '', postFlags, 'post');
  const ctaEl = el('bc-cta');
  if (ctaEl) ctaEl.innerHTML = _bcHighlightFlags(con.cta || '', postFlags, 'cta');

  el('bc-post')?.querySelectorAll('.bc-flag').forEach(m => m.addEventListener('click', e => { e.stopPropagation(); _bcShowFix(m); }));
  el('bc-cta')?.querySelectorAll('.bc-flag').forEach(m => m.addEventListener('click', e => { e.stopPropagation(); _bcShowFix(m); }));

  const accEl = el('bc-accordions');
  if (accEl) {
    accEl.innerHTML = _bcAccordion('Hashtags', _escHtml(con.hashtags || ''), 'bc-acc-tags') +
      _bcAccordion('Video script', _escHtml(con.script || ''), 'bc-acc-script');
    accEl.querySelectorAll('.bc-acc-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const t = document.getElementById(btn.dataset.target);
        const a = btn.querySelector('.bc-acc-arrow');
        if (!t) return;
        const open = t.style.display !== 'none';
        t.style.display = open ? 'none' : 'block';
        if (a) a.style.transform = open ? '' : 'rotate(90deg)';
      });
    });
  }

  // Populate editable image description field
  const imgDescEl = el('bc-img-desc');
  if (imgDescEl) imgDescEl.textContent = con.thumbnailIdea || '';

  // Show regen counter
  const IMAGE_REGEN_LIMIT = 3;
  const regenUsed = item.image_regen_count || 0;
  const regenLeft = Math.max(0, IMAGE_REGEN_LIMIT - regenUsed);
  _bcUpdateRegenCounter(regenUsed, regenLeft);

  if (_bcImageUrl) {
    const p = el('bc-img-preview'), c = el('bc-img-container'), b = el('bc-gen-img'), r = el('bc-img-regen');
    if (p) p.src = _bcImageUrl; if (c) c.style.display = 'block'; if (b) b.style.display = 'none';
    if (r) r.style.display = regenLeft > 0 ? 'inline-flex' : 'none';
  } else {
    const c = el('bc-img-container'), b = el('bc-gen-img');
    if (c) c.style.display = 'none';
    if (b) { b.style.display = regenLeft > 0 ? 'inline-flex' : 'none'; }
  }
}

function _bcUpdateRegenCounter(used, remaining) {
  const counterEl = el('bc-img-regen-counter');
  if (!counterEl) return;
  const IMAGE_REGEN_LIMIT = 3;
  if (used === 0) {
    counterEl.textContent = '';
    counterEl.style.display = 'none';
  } else if (remaining > 0) {
    counterEl.textContent = remaining + ' of ' + IMAGE_REGEN_LIMIT + ' generations remaining';
    counterEl.style.display = 'inline';
    counterEl.style.color = remaining === 1 ? 'var(--amber, #d97706)' : 'var(--ink-4)';
  } else {
    counterEl.textContent = 'Generation limit reached — edit the description above to unlock';
    counterEl.style.display = 'inline';
    counterEl.style.color = 'var(--ink-3)';
  }
}

function _bcHighlightFlags(text, flags, field) {
  if (!text || !flags.length) return _escHtml(text);
  const hits = flags.filter(f => f.location === field || (field === 'post' && f.location === 'unknown'));
  if (!hits.length) return _escHtml(text);
  let r = _escHtml(text);
  [...hits].sort((a,b) => b.triggered.length - a.triggered.length).forEach(flag => {
    const t   = _escHtml(flag.triggered);
    const fix = _escHtml(_getComplianceFix(flag.authority, flag.triggered, flag.cleanMessage) || '');
    const auth = _escHtml(flag.authority);
    const msg  = _escHtml(flag.cleanMessage);
    r = r.replace(new RegExp(_escRx(t), 'gi'),
      `<mark class="bc-flag" data-t="${t}" data-a="${auth}" data-fix="${fix}" data-msg="${msg}" style="background:#fef3c7;color:#78350f;border-radius:3px;padding:0 3px;border-bottom:2px solid #f59e0b;cursor:pointer;">${t}</mark>`);
  });
  return r;
}

function _bcAccordion(label, bodyHtml, id) {
  return `<div style="border-top:1px solid var(--border);">
    <button class="bc-acc-toggle" data-target="${id}" style="width:100%;display:flex;align-items:center;justify-content:space-between;padding:13px 0;background:none;border:none;cursor:pointer;font-family:inherit;">
      <span style="font-size:12px;font-weight:600;color:var(--ink-2);">${label}</span>
      <span class="bc-acc-arrow" style="font-size:11px;color:var(--ink-4);transition:transform .2s;">▸</span>
    </button>
    <div id="${id}" style="display:none;padding-bottom:14px;font-size:13px;color:var(--ink-2);line-height:1.75;white-space:pre-wrap;word-break:break-word;">${bodyHtml}</div>
  </div>`;
}

function _bcShowFix(mark) {
  _bcActiveMark = mark;
  const auth = mark.dataset.a || '';
  const fix  = mark.dataset.fix || '';
  const panel = el('bc-fix-panel'); if (!panel) return;
  const authEl = el('bc-fix-authority'); if (authEl) authEl.textContent = auth;
  const txtEl  = el('bc-fix-text');     if (txtEl)  txtEl.textContent  = fix || 'Remove or rephrase this term.';
  panel.style.display = 'block';
  panel.scrollIntoView({ behavior:'smooth', block:'nearest' });
  el('bc-fix-accept').onclick = () => _bcApplyFix(_bcActiveMark, _rmExtractReplacement(fix, mark.dataset.t || ''));
  el('bc-fix-keep').onclick   = _bcCloseFix;
}

function _bcCloseFix() {
  const p = el('bc-fix-panel'); if (p) p.style.display = 'none';
  _bcActiveMark = null;
}

function _bcApplyFix(mark, text) {
  if (!mark || !mark.parentNode) return;
  if (text === '') mark.parentNode.removeChild(mark);
  else mark.parentNode.replaceChild(document.createTextNode(text), mark);
  _bcCloseFix();
  _bcUpdateComplianceBar();
}

function _bcUpdateComplianceBar() {
  const remaining = (el('bc-post')?.querySelectorAll('.bc-flag').length || 0) +
                    (el('bc-cta')?.querySelectorAll('.bc-flag').length  || 0);
  const bar = el('bc-compliance-bar'), dot = el('bc-comp-dot'), txt = el('bc-comp-text'), hint = el('bc-edit-hint');
  if (remaining === 0 && bar) {
    bar.style.background = 'var(--green-dim)'; bar.style.borderColor = 'rgba(26,127,75,0.2)';
    if (dot) dot.style.background = 'var(--green)';
    if (txt) { txt.style.color = 'var(--green)'; txt.textContent = 'Pro-Reviewed — all notes resolved.'; }
    if (hint) hint.style.display = 'none';
  }
}

function _bcReadEdited() {
  function getText(id) {
    const e = el(id); if (!e) return '';
    const c = e.cloneNode(true);
    c.querySelectorAll('.bc-flag').forEach(m => m.replaceWith(document.createTextNode(m.textContent)));
    return (c.innerText || c.textContent || '').trim();
  }
  return { ...(_bcItem?.content || {}),
    headline: getText('bc-headline') || _bcItem?.content?.headline || '',
    post:     getText('bc-post')     || _bcItem?.content?.post     || '',
    cta:      getText('bc-cta')      || _bcItem?.content?.cta      || '',
  };
}

function _bcShowChannels() {
  _bcShowScreen('channels');
  const oauthConns    = JSON.parse(localStorage.getItem('hb_oauth_connections') || '{}');
  const connectedIds  = new Set(Object.entries(oauthConns).filter(([,v]) => v && v.connected).map(([k]) => k));
  const activePlats   = getActivePlatforms().map(p => p.id);
  const grid = el('bc-platform-grid'); if (!grid) return;
  grid.innerHTML = '';
  _bcSelectedPlts = new Set();

  // Reddit never allows auto-posting — always copy only
  const COPY_ONLY_ALWAYS = new Set(['reddit']);
  // Platforms where direct posting is not yet built — show "coming soon"
  const COMING_SOON = new Set(['instagram', 'tiktok', 'nextdoor']);

  // ── Section 1: Ready to broadcast (OAuth-connected, pre-selected) ──────────
  const broadcastIds = activePlats.filter(pid => connectedIds.has(pid));

  if (broadcastIds.length === 0 && activePlats.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1;padding:16px;background:var(--bg-sunken);border-radius:12px;font-size:13px;color:var(--ink-3);line-height:1.6;">No platforms selected yet. <a href="#" onclick="closeReviewModal();navigateTo('profile-panel');return false;" style="color:var(--gold);font-weight:600;">Set up Your Platforms in Profile →</a></div>`;
    _bcUpdateBroadcastBtn();
    return;
  }

  if (broadcastIds.length > 0) {
    const sectionLabel = document.createElement('div');
    sectionLabel.style.cssText = 'grid-column:1/-1;font-size:11px;font-weight:700;color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px;';
    sectionLabel.textContent = 'Ready to broadcast';
    grid.appendChild(sectionLabel);

    broadcastIds.forEach(pid => {
      const m = _bcPlatMeta[pid]; if (!m) return;
      const card = document.createElement('div');
      card.className = 'bc-plt-card on'; card.dataset.pid = pid;
      _bcSelectedPlts.add(pid);
      card.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between;">
        <div style="width:34px;height:34px;border-radius:8px;background:${m.bg};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:${m.fg};">${m.icon}</div>
        <span class="bc-plt-check">✓</span>
      </div>
      <div class="bc-plt-name">${m.label}</div>
      <div class="bc-plt-status">Connected</div>`;
      card.addEventListener('click', () => {
        if (_bcSelectedPlts.has(pid)) { _bcSelectedPlts.delete(pid); card.classList.remove('on'); }
        else { _bcSelectedPlts.add(pid); card.classList.add('on'); }
        _bcUpdateBroadcastBtn();
      });
      grid.appendChild(card);
    });
  }

  // ── Section 2: Copy & paste (active in Profile but not OAuth-connected) ────
  const copyIds = activePlats.filter(pid => !connectedIds.has(pid));

  if (copyIds.length > 0) {
    const sep = document.createElement('div');
    sep.style.cssText = 'grid-column:1/-1;margin-top:' + (broadcastIds.length > 0 ? '16px' : '0') + ';margin-bottom:2px;';
    sep.innerHTML = `<div style="font-size:11px;font-weight:700;color:var(--ink-3);text-transform:uppercase;letter-spacing:.06em;">Copy &amp; paste</div>
      <div style="font-size:11px;color:var(--ink-4);margin-top:2px;">Tap a card to copy formatted text for that platform.</div>`;
    grid.appendChild(sep);

    copyIds.forEach(pid => {
      const m = _bcPlatMeta[pid] || { label:pid, icon:pid.slice(0,2).toUpperCase(), bg:'var(--bg-sunken)', fg:'var(--ink-3)' };
      const isReddit    = COPY_ONLY_ALWAYS.has(pid);
      const isComingSoon = COMING_SOON.has(pid);
      const statusText  = isReddit ? 'Copy only — Reddit policy' : isComingSoon ? 'Direct posting coming soon' : 'Copy text to post manually';
      const card = document.createElement('div');
      card.className = 'bc-plt-card'; card.dataset.pid = pid;
      card.style.cssText = 'opacity:0.85;cursor:pointer;';
      card.innerHTML = `<div style="display:flex;align-items:center;justify-content:space-between;">
        <div style="width:34px;height:34px;border-radius:8px;background:${m.bg};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:${m.fg};">${m.icon}</div>
        <span style="font-size:18px;color:var(--ink-4);">⎘</span>
      </div>
      <div class="bc-plt-name">${m.label}</div>
      <div class="bc-plt-status" style="color:var(--ink-4);font-size:10px;">${statusText}</div>`;
      card.addEventListener('click', () => {
        // Copy the platform-formatted content to clipboard
        const edited = _bcReadEdited();
        const text   = _rmFmtPlatform(edited, pid);
        navigator.clipboard.writeText(text).then(() => {
          const statusEl = card.querySelector('.bc-plt-status');
          const orig = statusEl?.textContent;
          card.classList.add('on');
          if (statusEl) statusEl.textContent = '✓ Copied!';
          setTimeout(() => { card.classList.remove('on'); if (statusEl) statusEl.textContent = orig; }, 2000);
        }).catch(() => { showToast('Copy failed — please try again.'); });
      });
      grid.appendChild(card);
    });
  }

  // ── Add platform card ───────────────────────────────────────────────────────
  const addCard = document.createElement('div');
  addCard.className = 'bc-plt-card add';
  addCard.style.cssText = 'min-height:88px;';
  addCard.innerHTML = `<div style="font-size:24px;font-weight:300;color:var(--ink-5);line-height:1;">+</div><div style="font-size:11px;color:var(--ink-3);margin-top:4px;">Add platform</div>`;
  addCard.addEventListener('click', () => { closeReviewModal(); navigateTo('profile-panel'); });
  grid.appendChild(addCard);

  _bcUpdateBroadcastBtn();
}

function _bcUpdateBroadcastBtn() {
  const btn = el('bc-broadcast-btn'); if (!btn) return;
  const n = _bcSelectedPlts.size;
  btn.textContent = n === 0 ? 'Select at least one channel' : `Broadcast to ${n} channel${n > 1 ? 's' : ''} →`;
  btn.disabled    = n === 0;
  btn.style.opacity = n === 0 ? '0.5' : '1';
}

async function _bcDoBroadcast() {
  _bcShowScreen('broadcasting');
  const edited    = _bcReadEdited();
  const platforms = [..._bcSelectedPlts];
  const list = el('bc-bcast-list'); if (!list) return;
  list.innerHTML = '';
  const posted = [];

  platforms.forEach(pid => {
    const m = _bcPlatMeta[pid] || { icon:pid.slice(0,2).toUpperCase(), bg:'var(--blue-dim)', fg:'var(--blue)', label:pid };
    const row = document.createElement('div');
    row.className = 'bc-bcast-row'; row.id = 'bcrow-' + pid;
    row.innerHTML = `<div style="width:32px;height:32px;border-radius:8px;background:${m.bg};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:${m.fg};flex-shrink:0;">${m.icon}</div>
      <div style="flex:1;font-size:13px;font-weight:600;color:var(--ink);">${m.label}</div>
      <div id="bcst-${pid}" style="font-size:12px;color:var(--ink-3);">Sending…</div>`;
    list.appendChild(row);
  });

  for (const pid of platforms) {
    await new Promise(r => setTimeout(r, posted.length > 0 ? 900 : 0));
    try {
      const post     = _rmFmtPlatform(edited, pid);
      const imageUrl = _bcImageUrl || _bcItem?.image_url || null;
      const lib      = await fetchLibrary();
      const live     = lib.find(x => String(x.id) === String(_bcItem?.id)) || _bcItem;
      const r = await authFetch(BACKEND_URL + '/social/post', {
        method:'POST', body:JSON.stringify({ platform:pid, content:post, library_item_id:live?.id, image_url:imageUrl })
      });
      if (!r.ok) throw new Error();
      const row = el('bcrow-' + pid); const st = el('bcst-' + pid);
      if (row) row.classList.add('live');
      if (st) { st.textContent = '✓ Live'; st.style.color = 'var(--green)'; st.style.fontWeight = '600'; }
      posted.push(pid);
    } catch(e) {
      const st = el('bcst-' + pid);
      if (st) { st.textContent = 'Failed'; st.style.color = 'var(--red,#b91c1c)'; }
    }
  }

  // Mark item as published in the library if at least one platform succeeded
  if (posted.length > 0 && _bcItem?.id) {
    authFetch(BACKEND_URL + '/library/' + _bcItem.id, {
      method: 'PATCH',
      body:   JSON.stringify({
        status:      'published',
        publishedAt: new Date().toISOString(),
        copiedPlatforms: posted,
      }),
    }).catch(() => {}); // Best-effort — never block the success screen
  }

  await new Promise(r => setTimeout(r, 600));
  _bcShowLive(posted);
}

async function _bcApprove() {
  if (!_bcItem) return;
  const isMobile = window.innerWidth < 680;
  const item     = _bcItem;

  // Save any edits first
  const edited = _bcReadEdited();
  try {
    await authFetch(BACKEND_URL + '/library/' + item.id, {
      method:'PATCH',
      body: JSON.stringify({ content:edited, status:'approved', approvedAt:new Date().toISOString(), editedAt:new Date().toISOString() })
    });
  } catch(e) {
    showToast('Could not approve — please try again.');
    return;
  }

  if (isMobile) {
    // Mobile: stay in panel, show confirmation + Go Live option
    const bar = el('bc-action-bar');
    if (bar) {
      bar.innerHTML = `<div style="max-width:680px;margin:0 auto;text-align:center;padding:8px 0 4px;">
        <div style="font-size:22px;margin-bottom:6px;">✓</div>
        <div style="font-size:15px;font-weight:700;color:var(--green);margin-bottom:4px;">Approved</div>
        <div style="font-size:13px;color:var(--ink-3);margin-bottom:18px;">Ready to publish whenever you are.</div>
        <button onclick="_bcShowChannels()" style="width:100%;padding:14px;font-size:15px;font-weight:600;background:var(--blue);color:#fff;border:none;border-radius:14px;cursor:pointer;font-family:inherit;margin-bottom:10px;">Go live → Publish now</button>
        <button onclick="closeReviewModal();renderLibrary();" style="width:100%;padding:11px;font-size:13px;font-weight:500;color:var(--ink-3);background:var(--bg-sunken);border:1px solid var(--border);border-radius:12px;cursor:pointer;font-family:inherit;">Done — back to Records</button>
      </div>`;
    }
  } else {
    // Desktop: close panel, refresh library, scroll approved item to top
    closeReviewModal();
    await renderLibrary();
    showToast('✓ Approved — post saved to your library.');
    // Scroll the approved item into view
    setTimeout(() => {
      const itemEl = document.querySelector(`[data-item-id="${item.id}"]`);
      if (itemEl) itemEl.scrollIntoView({ behavior:'smooth', block:'start' });
    }, 300);
  }
}

function _bcShowLive(postedPids) {
  _bcShowScreen('live');
  const checkEl = el('bc-check');
  if (checkEl) { checkEl.textContent = '✓'; checkEl.classList.add('bc-check-pop'); }

  const postedList = el('bc-posted-list'); if (!postedList) return;
  postedList.innerHTML = '';
  const label = document.createElement('div');
  label.style.cssText = 'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:var(--ink-4);margin-bottom:10px;';
  label.textContent = 'Posted to';
  postedList.appendChild(label);

  postedPids.forEach(pid => {
    const m = _bcPlatMeta[pid] || { icon:pid.slice(0,2).toUpperCase(), bg:'var(--blue-dim)', fg:'var(--blue)', label:pid };
    const row = document.createElement('div');
    row.className = 'bc-posted-row';
    row.innerHTML = `<div style="width:28px;height:28px;border-radius:6px;background:${m.bg};display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:${m.fg};flex-shrink:0;">${m.icon}</div>
      <div style="font-size:13px;font-weight:600;color:var(--green);flex:1;">${m.label}</div>
      <div style="font-size:11px;color:var(--green);">View post →</div>`;
    postedList.appendChild(row);
  });

  // Fetch real identity score — show placeholder while loading
  const cir   = el('bc-cir-score');
  const delta = el('bc-cir-delta');
  const bar   = el('bc-cir-bar');
  if (cir)   cir.textContent   = '—';
  if (delta) delta.textContent = 'calculating…';

  const isDemo = localStorage.getItem('hb_demo_mode') === 'true';
  if (isDemo) {
    // Demo mode — show demo score
    if (cir)   cir.textContent   = '74';
    if (delta) delta.textContent = '+2 this post';
    setTimeout(() => { if (bar) bar.style.width = '74%'; }, 300);
  } else {
    authFetch(BACKEND_URL + '/identity/score', {
      method: 'POST',
      body:   JSON.stringify({}),
    }).then(r => r.ok ? r.json() : null).then(data => {
      if (!data) return;
      const score = data.score ?? data.total ?? 0;
      if (cir)   cir.textContent   = String(score);
      if (delta) delta.textContent = 'Identity Strength Score';
      setTimeout(() => { if (bar) bar.style.width = score + '%'; }, 300);
    }).catch(() => {
      if (cir)   cir.textContent   = '—';
      if (delta) delta.textContent = 'Score unavailable';
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  el('bc-close')?.addEventListener('click', () => {
    closeReviewModal();
    navigateTo('content-engine-panel');
  });
  el('bc-back')?.addEventListener('click',  () => _bcShowScreen('review'));

  el('bc-approve')?.addEventListener('click', () => _bcApprove());

  el('bc-go-live')?.addEventListener('click', async () => {
    if (!_bcItem) return;
    // Save edits and approve FIRST — then show channels
    // This was the bug: going straight to _bcShowChannels() skipped approval
    // and left the item in 'pending' state in the database.
    const edited = _bcReadEdited();
    try {
      await authFetch(BACKEND_URL + '/library/' + _bcItem.id, {
        method: 'PATCH',
        body:   JSON.stringify({
          content:    edited,
          status:     'approved',
          approvedAt: new Date().toISOString(),
          editedAt:   new Date().toISOString(),
        }),
      });
    } catch(e) {
      showToast('Could not approve — please check your connection and try again.');
      return;
    }
    // Approval saved — now open channel selector
    _bcShowChannels();
  });

  el('bc-save-draft')?.addEventListener('click', () => { closeReviewModal(); showToast('Saved to library.'); });

  el('bc-delete')?.addEventListener('click', async () => {
    if (!_bcItem) return;
    if (!confirm('Delete this post?')) return;
    const isDemo = localStorage.getItem('hb_demo_mode') === 'true';
    if (isDemo) { window._demoLibrary = (window._demoLibrary||[]).filter(x=>String(x.id)!==String(_bcItem.id)); }
    else { await apiDeleteLibraryItem(_bcItem.id).catch(()=>{}); renderLibrary(); }
    closeReviewModal();
  });

  el('bc-regen')?.addEventListener('click', () => { if (_bcItem) _bcRegenerate(_bcItem); });

  el('bc-gen-img')?.addEventListener('click',   () => { if (_bcItem) _bcGenerateImage(_bcItem); });
  el('bc-img-regen')?.addEventListener('click', () => { if (_bcItem) _bcGenerateImage(_bcItem); });

  el('bc-broadcast-btn')?.addEventListener('click', _bcDoBroadcast);

  el('bc-copy-text')?.addEventListener('click', () => {
    const edited = _bcReadEdited();
    const text   = [edited.headline, edited.post, edited.cta].filter(Boolean).join('\n\n');
    navigator.clipboard.writeText(text).then(() => {
      const btn = el('bc-copy-text');
      if (btn) { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy text', 2000); }
    }).catch(() => showToast('Copy failed — please select and copy manually.'));
  });

  el('bc-done')?.addEventListener('click', () => { _reviewModalOrigin = null; closeReviewModal(); navigateTo('home-panel'); renderHomeDashboard(); });
  el('bc-go-back')?.addEventListener('click', () => {
    const origin = _reviewModalOrigin;
    _reviewModalOrigin = null;
    closeReviewModal();
    if (origin === 'home') {
      navigateTo('home-panel');
      renderHomeDashboard();
    } else {
      // Clear content engine fields so agent starts fresh
      const sit = el('situation-select'); if (sit) sit.value = '';
      const tone = el('tone-select'); if (tone) tone.value = '';
      const len = el('length-select'); if (len) len.value = '';
      const persona = el('persona-select'); if (persona) persona.value = '';
      const out = el('ce-output'); if (out) out.innerHTML = '';
      const genBtn = el('generate-content-btn'); if (genBtn) genBtn.disabled = false;
      navigateTo('content-engine-panel');
    }
  });
});

async function _bcGenerateImage(item) {
  const IMAGE_REGEN_LIMIT = 3;
  const regenUsed = item?.image_regen_count || 0;
  if (regenUsed >= IMAGE_REGEN_LIMIT) {
    const st = el('bc-img-status');
    if (st) { st.style.display = 'block'; st.textContent = 'Generation limit reached (3 per post). Edit the image description above to unlock a new generation.'; }
    return;
  }

  const btn = el('bc-gen-img'), regen = el('bc-img-regen'), st = el('bc-img-status');
  if (btn)  { btn.disabled = true; btn.textContent = '⏳ Generating…'; }
  if (regen) regen.disabled = true;
  if (st)   { st.style.display = 'block'; st.textContent = 'Creating your image — this takes 15–45 seconds…'; }

  const saved = getSaved();
  const con   = item?.content || {};

  // Use the editable image description field — agent may have customised it
  const imgDescEl = el('bc-img-desc');
  const thumbnailIdea = (imgDescEl ? imgDescEl.textContent.trim() : '') || con.thumbnailIdea || '';

  try {
    const r = await authFetch(BACKEND_URL + '/image/generate', {
      method:'POST',
      body: JSON.stringify({
        library_item_id: item.id,
        thumbnail_idea:  thumbnailIdea,
        niche:           item?.niche || (saved.primaryNiches || [])[0] || 'real estate',
        market:          saved.market || '',
      })
    });

    if (r.status === 429) {
      // Regen limit hit server-side (race condition guard)
      if (st) st.textContent = 'Generation limit reached (3 per post). Edit the description above to unlock.';
      if (btn) { btn.disabled = false; btn.textContent = '🎨 Generate image'; }
      if (regen) regen.disabled = false;
      return;
    }
    if (!r.ok) throw new Error();

    const d = await r.json();
    _bcImageUrl = d.image_url;
    if (item) {
      item.image_url         = _bcImageUrl;
      item.image_regen_count = d.regen_count || (regenUsed + 1);
    }

    const p = el('bc-img-preview'), c = el('bc-img-container');
    if (p) p.src = _bcImageUrl; if (c) c.style.display = 'block';
    if (btn) btn.style.display = 'none';

    const newRemaining = d.regen_remaining ?? (IMAGE_REGEN_LIMIT - (item?.image_regen_count || 1));
    if (regen) {
      regen.disabled = false;
      regen.style.display = newRemaining > 0 ? 'inline-flex' : 'none';
    }
    _bcUpdateRegenCounter(item?.image_regen_count || 1, newRemaining);
    if (st) st.style.display = 'none';

  } catch(e) {
    if (st) st.textContent = 'Image generation failed — please try again.';
    if (btn) { btn.disabled = false; btn.textContent = '🎨 Generate image'; }
    if (regen) regen.disabled = false;
  }
}

// Parse a fix instruction and return the actual replacement text
function _rmExtractReplacement(fix, triggered) {
  if (!fix) return "";
  const f = fix.trim();
  if (/^remove\b/i.test(f)) return "";
  const withMatch = f.match(/replace\s+["\u201c\u201d]?.+?["\u201c\u201d]?\s+with\s+["\u201c\u201d]?(.+?)["\u201c\u201d]?[.\s]*$/i);
  if (withMatch) return withMatch[1].trim().replace(/[."""']+$/, "");
  return "";
}

// Format post content for a specific platform
function _rmFmtPlatform(con, p) {
  const post = con.post||"", cta = con.cta||"", tags = con.hashtags||"", hl = con.headline||"", sc = con.script||"";
  if (p === "linkedin") return [hl, post, cta, tags].filter(Boolean).join("\n\n");
  if (p === "youtube")  return [hl, sc||post, cta].filter(Boolean).join("\n\n");
  return [post, cta].filter(Boolean).join("\n\n");
}

async function _bcRegenerate(item) {
  let payload, focusNiche, isDemo;
  if (window._lastGeneratePayload) {
    ({ payload, focusNiche, isDemo } = window._lastGeneratePayload);
  } else {
    const saved = getSaved();
    focusNiche  = item?.niche || (saved.primaryNiches || [])[0] || 'Residential Buying & Selling';
    isDemo      = localStorage.getItem('hb_demo_mode') === 'true';
    payload     = {
      identity:     { primaryCategories:[focusNiche], subNichesByCategory:{}, trendPreferences:[] },
      agentProfile: ceAgentProfilePayload(),
      situation:    'Refresh and improve this piece of content for my market',
      persona:null, tone:null, length:'medium', content_mode:'agent', generation_mode:'guided',
    };
  }
  const oldId = item.id; payload.timestamp = new Date().toISOString();
  const postEl = el('bc-post');
  if (postEl) postEl.innerHTML = '<div style="padding:24px;text-align:center;color:var(--ink-4);font-size:13px;">Generating fresh content…</div>';
  try {
    const res = await authFetch(BACKEND_URL + '/content/generate-content', { method:'POST', body:JSON.stringify(payload) });
    if (!res.ok) throw new Error();
    const d  = await res.json();
    const cp = { headline:d.headline||'', thumbnailIdea:d.thumbnailIdea||'', hashtags:d.hashtags||'', post:d.post||'', cta:d.cta||'', script:d.script||'' };
    if (isDemo) {
      const ni = { id:'demo-'+Date.now(), niche:focusNiche, content:cp, compliance:d.compliance||null, status:'pending', created_at:new Date().toISOString(), is_demo:true };
      if (!window._demoLibrary) window._demoLibrary = [];
      window._demoLibrary.unshift(ni);
      window._demoLibrary = window._demoLibrary.filter(x => String(x.id) !== String(oldId));
      openReviewModal(ni);
    } else {
      const ni = await apiSaveLibraryItem(focusNiche, cp, d.compliance||null);
      apiDeleteLibraryItem(oldId).catch(()=>{});
      renderLibrary(); openReviewModal(ni);
    }
  } catch(e) { showToast('Regeneration failed — please try again.'); }
}




// ─────────────────────────────────────────────
// SECTION 28: WORKSPACE
// ─────────────────────────────────────────────
function loadIntoWorkspace(item) {
  activeLibraryItemId = item.id;
  [["ws-headline","headline"],["ws-thumbnail","thumbnailIdea"],["ws-hashtags","hashtags"],["ws-post","post"],["ws-cta","cta"],["ws-script","script"]].forEach(([id,key]) => {
    const e = el(id); if (e) { e.textContent = item.content[key]||""; e.dataset.original = item.content[key]||""; }
  });
  const saveBtn = el("ws-save-btn"); if (saveBtn) saveBtn.textContent = "Save Changes";
  const empty   = el("workspace-empty"); const content = el("workspace-content");
  if (empty)   empty.style.display   = "none";
  if (content) content.style.display = "block";
}
function getWorkspaceContent() {
  return { headline:el("ws-headline")?.textContent||"", thumbnailIdea:el("ws-thumbnail")?.textContent||"", hashtags:el("ws-hashtags")?.textContent||"", post:el("ws-post")?.textContent||"", cta:el("ws-cta")?.textContent||"", script:el("ws-script")?.textContent||"" };
}
el("ws-back-btn")?.addEventListener("click", () => navigateTo("library-panel"));

el("ws-recheck-btn")?.addEventListener("click", async () => {
  const btn = el("ws-recheck-btn"); if (!activeLibraryItemId) return;
  btn.disabled = true; btn.textContent = "Checking…";
  const result = el("ws-compliance-result");
  if (result) { result.style.display = "block"; result.innerHTML = '<div style="font-size:12px;color:var(--muted);">Running compliance check…</div>'; }
  try {
    const res = await authFetch(`${BACKEND_URL}/compliance/check`, {
      method: "POST",
      body: JSON.stringify({ item_id: activeLibraryItemId, content_mode: getContentContext() === "hb_marketing" ? "b2b" : "agent" })
    });
    if (!res.ok) throw new Error(`${res.status}`);
    const data = await res.json();
    const verdict = data.overallStatus || data.overall_verdict || "review";
    const col   = { compliant:"var(--green)", pass:"var(--green)", review:"var(--amber)", attention:"var(--red)", fail:"var(--red)" };
    const icon  = { compliant:"✓", pass:"✓", review:"⚠", attention:"✗", fail:"✗" };
    const label = { compliant:"Pro-Reviewed", pass:"Pro-Reviewed", review:"Needs Review", attention:"Attention Required", fail:"Attention Required" };
    // Clear fix banner — replace with result
    window._pendingComplianceFix = null;
    if (result) result.innerHTML = `
      <div style="font-size:13px;font-weight:700;color:${col[verdict]||col.review};margin-bottom:8px;">${icon[verdict]||"⚠"} Compliance Re-check: ${label[verdict]||"Needs Review"}</div>
      ${(data.notes||[]).filter(n=>!n.toLowerCase().includes("state rules")&&!n.toLowerCase().includes("jurisdiction")).map(n=>`<div style="font-size:12px;color:var(--ink-2);margin-bottom:4px;">• ${n}</div>`).join("")}
      <div style="margin-top:10px;font-size:11px;color:var(--muted);">Checked ${new Date().toLocaleTimeString()}</div>
    `;
    // Update cached library item so approve gate sees fresh data
    _cachedLibrary = null;
    btn.textContent = "Re-check Again";
    btn.disabled = false;
  } catch(e) {
    if (result) result.innerHTML = '<div style="font-size:12px;color:var(--red);">Re-check failed — please try again.</div>';
    btn.disabled = false; btn.textContent = "✓ Saved — Re-check Compliance";
  }
});

el("ws-save-btn")?.addEventListener("click", async () => {
  const btn = el("ws-save-btn"); if (!activeLibraryItemId) return;
  btn.disabled=true; btn.textContent="Saving…";
  try {
    await apiPatchLibraryItem(activeLibraryItemId, { content:getWorkspaceContent(), editedAt:new Date().toISOString() });
    btn.textContent="Saved ✓";
    // Show re-check button instead of navigating away
    const recheckBtn = el("ws-recheck-btn");
    if (recheckBtn) recheckBtn.style.display = "inline-flex";
    setTimeout(() => { btn.disabled=false; btn.textContent="Save Changes"; }, 1500);
  } catch(e) { btn.disabled=false; btn.textContent="Save Changes"; }
});
el("ws-copy-all")?.addEventListener("click", () => {
  const btn = el("ws-copy-all");
  const parts = [["HEADLINE","ws-headline"],["THUMBNAIL","ws-thumbnail"],["HASHTAGS","ws-hashtags"],["POST","ws-post"],["CTA","ws-cta"],["SCRIPT","ws-script"]].map(([l,id])=>`--- ${l} ---\n${el(id)?.textContent||""}`);
  navigator.clipboard.writeText(parts.join("\n\n"));
  btn.textContent="Copied!"; setTimeout(()=>btn.textContent="Copy All",1500);
});
document.addEventListener("click", e => {
  if (e.target.id==="ws-distribute-btn") openDistribution(getWorkspaceContent(), activeNicheForGenerate||(getSaved().primaryNiches||[])[0]||"");
  if (e.target.dataset.distOpen) fetchLibrary().then(lib => { const item = lib.find(x=>String(x.id)===String(e.target.dataset.distOpen)); if (item) openDistribution(item.content,item.niche,item.id); });
});

// ─────────────────────────────────────────────
// SECTION 29: DISTRIBUTION MODAL
// ─────────────────────────────────────────────
function openDistribution(content, nicheLabel, libraryItemId) {
  activeDistributionItemId   = libraryItemId || null;
  copiedPlatformsThisSession = [];
  const saved    = getSaved();
  const socials  = getSocials();

  // Get CIR ID for this library item — appended to post as verification stamp
  const cachedItem = (_cachedLibrary||[]).find(x=>String(x.id)===String(libraryItemId));
  const cirId      = cachedItem?.cir_id || null;
  // Get user ID for profile link
  const hbUser2  = JSON.parse(localStorage.getItem("hb_user") || "null");
  const userId2  = hbUser2?.id || null;
  const cirStamp = cirId
    ? `\u2713 CIR\u2122 Verified \u00b7 homebridgegroup.co/agent-profile.html?id=${userId2}`
    : "";

  const identity = {
    name: saved.agentName||"", brokerage:saved.brokerage||"", market:saved.market||"",
    niche:nicheLabel||(saved.primaryNiches||[])[0]||"", disclaimer:getDisclaimer(),
    cirStamp: cirStamp,
    socials: { linkedin:socials.linkedin||"", instagram:socials.instagram||"", facebook:socials.facebook||"", tiktok:socials.tiktok||"", youtube:socials.youtube||"", twitter:socials.twitter||"", threads:socials.threads||"", reddit:socials.reddit||"", google:socials.google||"", nextdoor:socials.nextdoor||"" }
  };
  const modal = el("distribution-modal"); const body = el("distribution-modal-body");
  if (!modal || !body) return;
  body.innerHTML = "";
  const activePlatformIds = getActivePlatforms().map(p=>p.id);
  const savedActive       = (getSaved().platforms||[]).map(p=>p.id);
  const userIds           = activePlatformIds.length > 0 ? activePlatformIds : savedActive;
  const toShow = (userIds.length > 0) ? PLATFORMS.filter(p=>p.status==="active"&&userIds.includes(p.id)) : PLATFORMS.filter(p=>p.status==="active");
  // Check which platforms have OAuth connections
  const oauthConns = JSON.parse(localStorage.getItem("hb_oauth_connections") || "{}");

  toShow.forEach(p => {
    const formatted = p.format(content, identity);
    const isOAuthConnected = OAUTH_PLATFORMS.includes(p.id) && oauthConns[p.id]?.connected;
    const card = document.createElement("div"); card.className = "dist-card";

    // Build action row — direct post button for connected platforms, copy for others
    let actionHTML;
    if (isOAuthConnected) {
      actionHTML = `<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
        <button class="btn-primary dist-post-btn" data-platform="${p.id}" data-label="${p.label}" style="padding:10px 24px;font-size:13px;">Post to ${p.label} →</button>
        <button class="btn-secondary dist-copy-btn" data-platform="${p.id}" data-label="${p.label}" style="font-size:12px;padding:8px 16px;">Copy</button>
      </div>`;
    } else {
      actionHTML = `<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
        <button class="btn-secondary dist-copy-btn" data-platform="${p.id}" data-label="${p.label}">Copy for ${p.label}</button>
        ${OAUTH_PLATFORMS.includes(p.id) ? `<a href="#" onclick="closeDistribution();navigateTo('profile-panel');setTimeout(()=>{const b=document.getElementById('acc-body-platforms');if(b&&b.style.display==='none')toggleAccordion('platforms');},400);return false;" style="font-size:12px;color:var(--blue);text-decoration:none;">Connect to post directly →</a>` : ""}
      </div>`;
    }

    card.innerHTML = `<div class="dist-card-header"><div class="dist-card-title">${p.icon} ${p.label}</div><div class="dist-card-hint">${p.hint}</div></div>
      <div class="dist-card-body" id="dist-${p.id}" contenteditable="true">${formatted}</div>
      ${actionHTML}`;
    body.appendChild(card);

    // Copy button handler
    card.querySelector(".dist-copy-btn")?.addEventListener("click", btn => {
      const textEl = el(`dist-${p.id}`); if (!textEl) return;
      navigator.clipboard.writeText(textEl.textContent||"").then(() => {
        const b = card.querySelector(".dist-copy-btn");
        b.textContent="Copied ✓"; b.style.cssText="background:var(--blue);color:#fff;";
        setTimeout(()=>{b.textContent=`Copy for ${p.label}`;b.style.cssText="";},2000);
        if (!copiedPlatformsThisSession.includes(p.label)) copiedPlatformsThisSession.push(p.label);
        if (activeDistributionItemId) { const item = (_cachedLibrary||[]).find(x=>String(x.id)===String(activeDistributionItemId)); const cur=item?.copiedPlatforms||[]; if (!cur.includes(p.label)) apiPatchLibraryItem(activeDistributionItemId,{copiedPlatforms:[...cur,p.label]}).catch(()=>{}); }
      });
    });

    // Direct post button handler
    card.querySelector(".dist-post-btn")?.addEventListener("click", async btn => {
      const textEl = el(`dist-${p.id}`); if (!textEl) return;
      const postText = textEl.textContent || "";
      const b = card.querySelector(".dist-post-btn");
      b.textContent = "Posting…"; b.disabled = true;
      try {
        // Include image_url if one was generated
        const lib2 = _cachedLibrary || [];
        const postItem = lib2.find(x => String(x.id) === String(activeDistributionItemId));
        const imageUrl = postItem?.image_url || null;
        // Include org_urn when in marketing context (posts to HB LinkedIn Company Page)
        const isMarketing = getViewContext() === "marketing";
        const orgUrn = isMarketing && p.id === "linkedin" ? "urn:li:organization:51723296" : null;
        const res = await authFetch(BACKEND_URL + "/social/post", {
          method: "POST",
          body: JSON.stringify({ platform: p.id, content: postText, library_item_id: activeDistributionItemId, image_url: imageUrl, org_urn: orgUrn })
        });
        if (!res.ok) throw new Error("Post failed");
        const postResult = await res.json().catch(() => ({}));

        if (postResult.action === "script_ready") {
          // YouTube — script prepared, agent needs to film and upload
          b.textContent = "✓ Script ready";
          b.style.cssText = "background:var(--ink);color:#fff;padding:10px 24px;font-size:13px;";
          const msgEl = document.createElement("div");
          msgEl.style.cssText = "margin-top:10px;font-size:13px;color:var(--ink-3);line-height:1.5;padding:12px 16px;background:var(--bg);border-radius:8px;";
          msgEl.innerHTML = postResult.message + ' <a href="https://studio.youtube.com" target="_blank" style="color:var(--blue);font-weight:600;">Open YouTube Studio →</a>';
          card.appendChild(msgEl);
        } else {
          b.textContent = "✓ Published";
          b.style.cssText = "background:var(--green);color:#fff;padding:10px 24px;font-size:13px;";
        }

        if (activeDistributionItemId) {
          await apiPatchLibraryItem(activeDistributionItemId, { status: "published", publishedAt: new Date().toISOString() });
          renderLibrary();
        }
        if (postResult.action !== "script_ready") setTimeout(() => closeDistribution(), 1500);
      } catch(err) {
        b.textContent = "Post to " + p.label + " →";
        b.disabled = false;
        showToast("Posting failed. Check your connection and try again.");
      }
    });
  });
  // Show "connect your platforms" notice if no platforms connected
  const connectNotice = el("dist-connect-notice");
  if (connectNotice) {
    const hasPlatforms = toShow.length > 0;
    connectNotice.style.display = hasPlatforms ? "none" : "block";
  }
  modal.classList.add("visible"); document.body.style.overflow="hidden";
}
function closeDistribution() { el("distribution-modal")?.classList.remove("visible"); document.body.style.overflow=""; activeDistributionItemId=null; }
el("dist-modal-close")?.addEventListener("click", closeDistribution);
el("dist-done-btn")?.addEventListener("click", closeDistribution);
el("distribution-modal")?.addEventListener("click", e => { if (e.target.id==="distribution-modal") closeDistribution(); });
document.addEventListener("keydown", e => { if (e.key==="Escape") closeDistribution(); });
el("dist-mark-posted-btn")?.addEventListener("click", async () => {
  if (!activeDistributionItemId) { closeDistribution(); return; }
  try { await apiPatchLibraryItem(activeDistributionItemId, { status:"published", publishedAt:new Date().toISOString() }); }
  catch(err) { console.error("Mark posted error:", err); }
  closeDistribution(); renderLibrary();
});

// ─────────────────────────────────────────────
// SECTION 29B: BROKER PANEL TAB WIRING
// ─────────────────────────────────────────────

function initBrokerTabs() {
  const ctx    = getViewContext();
  const isTeam = ctx === "team" || (JSON.parse(localStorage.getItem("hb_user")||"null")?.role === "team");

  // Show/hide Activity tab (team only)
  const actBtn = el("broker-tab-activity");
  if (actBtn) actBtn.style.display = isTeam ? "inline-block" : "none";

  // Relabel Agents tab for team context
  const agentsBtn = el("broker-tab-agents");
  if (agentsBtn) agentsBtn.textContent = isTeam ? "Members" : "Agents";

  // Wire tab clicks
  document.querySelectorAll(".broker-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      // Update button styles
      document.querySelectorAll(".broker-tab").forEach(b => {
        b.style.borderBottomColor = "transparent";
        b.style.color = "var(--ink-3)";
      });
      btn.style.borderBottomColor = "var(--blue)";
      btn.style.color = "var(--blue)";
      // Show correct content panel
      document.querySelectorAll(".broker-tab-content").forEach(p => p.style.display = "none");
      const map = {
        overview:   "broker-tab-overview",
        agents:     "broker-tab-agents",
        compliance: "broker-tab-compliance",
        activity:   "broker-tab-activity-panel",
      };
      const target = el(map[tab]);
      if (target) target.style.display = "block";
      // Lazy-load compliance or activity on first open
      if (tab === "compliance") loadBrokerCompliance();
      if (tab === "activity")   loadTeamActivity();
    });
  });
}

async function loadBrokerCompliance() {
  const wrap = el("broker-compliance-list");
  if (!wrap) return;
  // Allow reload on filter — remove dataset.loaded guard
  wrap.innerHTML = '<div style="padding:24px;color:var(--ink-3);font-size:13px;">Loading compliance records…</div>';

  const isDemo = localStorage.getItem("hb_demo_mode") === "true";

  // ── Demo path ──────────────────────────────────────────────────────────
  if (isDemo) {
    const demoRecords = [
      { agent_name:"Brooke Callahan", cir_id:"CIR-20260301-A3F9D2", niche:"Relocation",
        headline:"Why Silicon Valley Engineers Keep Choosing South Congress Over Palo Alto",
        overall_status:"reviewed", approved_at:"2026-03-01" },
      { agent_name:"Brooke Callahan", cir_id:"CIR-20260303-B2E1C8", niche:"Residential Buying & Selling",
        headline:"The Rate Buydown Strategy Most Austin Buyers Still Haven't Heard Of",
        overall_status:"review-recommended", approved_at:"2026-03-03" },
      { agent_name:"James Whitfield",  cir_id:"CIR-20260228-F4A7B1", niche:"Seller Representation",
        headline:"Why Overpricing Your Home Still Costs You More in 2026",
        overall_status:"reviewed", approved_at:"2026-02-28" },
      { agent_name:"Dana Solis",       cir_id:"CIR-20260210-C9D3E5", niche:"Buyer Representation",
        headline:"First-Time Buyer Programs in Austin That Most Agents Don't Mention",
        overall_status:"reviewed", approved_at:"2026-02-10" },
    ];
    _renderBrokerComplianceList(wrap, demoRecords, "all");
    _wireBrokerComplianceFilters(wrap, demoRecords);
    return;
  }

  // ── Live path ──────────────────────────────────────────────────────────
  try {
    // First load all agents so we can populate the agent picker
    const ctx    = getViewContext();
    const user   = JSON.parse(localStorage.getItem("hb_user") || "null");
    const isTeam = ctx === "team" || user?.role === "team";
    const statsEndpoint = isTeam ? `${BACKEND_URL}/team/stats` : `${BACKEND_URL}/broker/office-stats`;
    const statsRes = await authFetch(statsEndpoint);
    const agents   = statsRes.ok ? ((await statsRes.json()).agents || []) : [];

    // Render filter bar with agent picker + date range
    const agentOptions = agents.map(a =>
      `<option value="${a.id}">${a.name || a.agent_name}</option>`
    ).join("");

    wrap.innerHTML = `
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px;">
        <select id="bc-agent-filter" style="font-size:12px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--white);color:var(--ink);font-family:inherit;">
          <option value="">All agents</option>${agentOptions}
        </select>
        <input type="date" id="bc-from" style="font-size:12px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--white);color:var(--ink);font-family:inherit;">
        <input type="date" id="bc-to"   style="font-size:12px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--white);color:var(--ink);font-family:inherit;">
        <button onclick="loadBrokerComplianceRecords()" style="font-size:12px;padding:6px 14px;border-radius:6px;background:var(--gold);color:#fff;border:none;cursor:pointer;font-family:inherit;font-weight:600;">Search</button>
        <button onclick="downloadBrokerCompliancePDF()" style="font-size:12px;padding:6px 14px;border-radius:6px;background:var(--white);color:var(--ink);border:1px solid var(--border);cursor:pointer;font-family:inherit;font-weight:600;">⬇ Download PDF</button>
      </div>
      <div id="bc-records-list"></div>`;

    // Load initial unfiltered records
    await loadBrokerComplianceRecords();
  } catch(e) {
    wrap.innerHTML = '<div style="padding:24px;color:var(--ink-3);font-size:13px;">Could not load compliance records.</div>';
  }
}

async function loadBrokerComplianceRecords() {
  const list    = document.getElementById("bc-records-list");
  if (!list) return;
  list.innerHTML = '<div style="padding:16px;color:var(--ink-3);font-size:13px;">Loading…</div>';
  const agentId = document.getElementById("bc-agent-filter")?.value || "";
  const from    = document.getElementById("bc-from")?.value || "";
  const to      = document.getElementById("bc-to")?.value   || "";
  try {
    const body = {};
    if (agentId) body.agent_id  = parseInt(agentId);
    if (from)    body.date_from = from;
    if (to)      body.date_to   = to;
    const res  = await authFetch(`${BACKEND_URL}/broker/compliance-history`, { method:"POST", body:JSON.stringify(body) });
    if (!res.ok) throw new Error();
    const data    = await res.json();
    const records = data.records || [];
    _renderBrokerComplianceList(list, records, "all");
  } catch(e) {
    list.innerHTML = '<div style="padding:16px;color:var(--red);font-size:13px;">Could not load records — please try again.</div>';
  }
}

async function downloadBrokerCompliancePDF() {
  const btn     = document.querySelector("[onclick='downloadBrokerCompliancePDF()']");
  const agentId = document.getElementById("bc-agent-filter")?.value || "";
  const from    = document.getElementById("bc-from")?.value || "";
  const to      = document.getElementById("bc-to")?.value   || "";
  if (!agentId) { showToast("Select a specific agent to download their compliance PDF."); return; }
  if (btn) { btn.disabled = true; btn.textContent = "Generating…"; }
  try {
    const res = await authFetch(`${BACKEND_URL}/broker/compliance-history/report`, {
      method:"POST",
      body: JSON.stringify({ agent_id:parseInt(agentId), date_from:from, date_to:to })
    });
    if (!res.ok) throw new Error();
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch(e) {
    showToast("Could not generate PDF — please try again.");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "⬇ Download PDF"; }
  }
}

function _renderBrokerComplianceList(wrap, records, filter) {
  const verdictBadge = v => {
    const map = {
      "reviewed":           ["#f0fdf4","#15803d","✓ Reviewed"],
      "review-recommended": ["#fffbeb","#b45309","⚠ Review"],
      "attention-required": ["#fef2f2","#b91c1c","✗ Attention"],
    };
    const [bg,color,label] = map[v] || ["#f8f7f5","#7a7470","—"];
    return `<span style="font-size:11px;font-weight:700;padding:2px 10px;border-radius:4px;background:${bg};color:${color};">${label}</span>`;
  };
  const filtered = filter === "all" ? records : records.filter(r => r.overall_status === filter);
  if (!filtered.length) {
    wrap.innerHTML = `<div style="padding:24px;color:var(--ink-3);font-size:13px;">${filter === "all" ? "No compliance records found." : "No items matching this filter."}</div>`;
    return;
  }
  wrap.innerHTML = filtered.map(r => `
    <div style="border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:8px;background:var(--white);">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
        <div style="flex:1;min-width:0;">
          <div style="font-size:12px;font-weight:700;color:var(--ink-3);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px;">${r.agent_name || ""}</div>
          <div style="font-size:13px;font-weight:600;color:var(--ink);margin-bottom:4px;line-height:1.4;">${r.headline || "Post"}</div>
          <div style="font-size:11px;color:var(--ink-3);">${r.niche || "—"} · ${(r.approved_at || "").slice(0,10)}</div>
          <div style="font-size:11px;font-weight:700;color:var(--gold);letter-spacing:0.04em;margin-top:3px;">${r.cir_id || ""}</div>
        </div>
        <div style="flex-shrink:0;">${verdictBadge(r.overall_status)}</div>
      </div>
    </div>`).join("");
}

function _wireBrokerComplianceFilters(wrap, rows) {
  document.querySelectorAll(".broker-compliance-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".broker-compliance-filter").forEach(b => {
        b.style.background = "none"; b.style.color = "var(--ink-3)"; b.style.borderColor = "var(--border)";
      });
      btn.style.background = "var(--gold)"; btn.style.color = "#fff"; btn.style.borderColor = "var(--gold)";
      _renderBrokerComplianceList(wrap, rows, btn.dataset.filter);
    });
  });
}

function viewBrokerContentRecord(itemId) {
  // Read-only content record view — broker oversight, not editorial control
  const modal = document.createElement("div");
  modal.id = "broker-content-record-modal";
  modal.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;padding:24px;";
  modal.innerHTML = `
    <div style="background:var(--white);border-radius:16px;max-width:600px;width:100%;max-height:80vh;overflow-y:auto;padding:28px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
        <div>
          <div style="font-size:16px;font-weight:700;color:var(--ink);">Content Record</div>
          <div style="font-size:12px;color:var(--ink-3);margin-top:2px;">Read-only oversight view</div>
        </div>
        <button onclick="document.getElementById('broker-content-record-modal').remove()"
          style="background:none;border:none;font-size:20px;color:var(--ink-3);cursor:pointer;">✕</button>
      </div>
      <div id="broker-record-body" style="font-size:13px;color:var(--ink-3);">Loading…</div>
    </div>`;
  document.body.appendChild(modal);
  authFetch(`${BACKEND_URL}/broker/agent-content?item_id=${itemId}`)
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      const item = data?.item || data;
      if (!item) { el("broker-record-body").textContent = "Record not found."; return; }
      const comp = item.compliance || "{}";
      el("broker-record-body").innerHTML = `
        <div style="margin-bottom:16px;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--ink-3);margin-bottom:6px;">Content</div>
          <div style="white-space:pre-wrap;line-height:1.7;color:var(--ink);background:var(--surface);border-radius:8px;padding:14px;font-size:13px;">${item.content||""}</div>
        </div>
        <div style="margin-bottom:16px;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--ink-3);margin-bottom:6px;">Compliance Record</div>
          <div style="white-space:pre-wrap;line-height:1.7;color:var(--ink);background:var(--surface);border-radius:8px;padding:14px;font-size:12px;font-family:monospace;">${typeof comp==="string"?comp:JSON.stringify(comp,null,2)}</div>
        </div>
        <div style="font-size:11px;color:var(--ink-3);">Status: ${item.status||"—"} · ${relativeTime(item.approved_at||item.saved_at)}</div>`;
    }).catch(() => { el("broker-record-body").textContent = "Could not load record."; });
}

async function loadTeamActivity() {
  const wrap = el("broker-activity-feed");
  if (!wrap || wrap.dataset.loaded) return;
  wrap.dataset.loaded = "1";
  try {
    const res = await authFetch(`${BACKEND_URL}/team/stats`);
    if (!res.ok) throw new Error();
    const agents = (await res.json()).agents || [];
    if (!agents.length) {
      wrap.innerHTML = '<div style="padding:24px;color:var(--ink-3);font-size:13px;">No team members yet.</div>';
      return;
    }
    // Pull recent content for each member and merge into chronological feed
    const allItems = [];
    for (const a of agents) {
      const cr = await authFetch(`${BACKEND_URL}/broker/agent-content?agent_id=${a.id}&limit=20`);
      if (!cr.ok) continue;
      const items = (await cr.json()).content || [];
      items.forEach(item => allItems.push({ ...item, _memberName: a.name || a.agent_name }));
    }
    allItems.sort((a,b) => new Date(b.saved_at||0) - new Date(a.saved_at||0));
    const top50 = allItems.slice(0, 50);
    const statusColor = { pending:"var(--amber)", approved:"var(--blue)", published:"var(--green)" };
    wrap.innerHTML = top50.map(item => `
      <div style="display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-bottom:1px solid var(--border);">
        <div style="flex-shrink:0;width:8px;height:8px;border-radius:50%;background:${statusColor[item.status]||"var(--ink-3)"};margin-top:5px;"></div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:12px;font-weight:700;color:var(--ink-3);">${item._memberName}</div>
          <div style="font-size:13px;color:var(--ink);margin:2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${(item.content||"").substring(0,100)}…</div>
          <div style="font-size:11px;color:var(--ink-3);">${item.status||""} · ${item.niche||""} · ${relativeTime(item.saved_at)}</div>
        </div>
      </div>`).join("") || '<div style="padding:24px;color:var(--ink-3);font-size:13px;">No activity yet.</div>';
  } catch(e) {
    wrap.innerHTML = '<div style="padding:24px;color:var(--ink-3);font-size:13px;">Could not load activity.</div>';
  }
}

// ─────────────────────────────────────────────
// SECTION 30: BROKER DASHBOARD
// ─────────────────────────────────────────────
async function loadBrokerDashboard() {
  if (localStorage.getItem("hb_demo_mode") === "true") { loadDemoBrokerView(); return; }
  const user  = JSON.parse(localStorage.getItem("hb_user") || "null");
  const isTeam = user?.role === "team" || getViewContext() === "team";

  // ── Init tab system ──────────────────────────────────────────────────────
  initBrokerTabs();

  // ── Update panel labels based on context ────────────────────────────────
  const panelTitle = document.querySelector("#broker-panel .panel-title");
  const panelSub   = document.querySelector("#broker-panel .panel-subtitle");
  const codeLabel  = document.querySelector(".office-code-label");
  const codeHint   = document.querySelector(".office-code-hint");
  const statSub    = document.querySelector("#broker-stat-agents + * .office-stat-sub, #broker-stat-tiles .office-stat-tile:first-child .office-stat-sub");
  const inviteTitle = document.querySelector("#broker-panel [style*='Invite']");

  if (isTeam) {
    if (panelTitle) panelTitle.textContent = "Team Dashboard";
    if (panelSub)   panelSub.textContent   = "Your team members, their content activity, and compliance — all in one place.";
    if (codeLabel)  codeLabel.textContent  = "Your Team Code";
    if (codeHint)   codeHint.textContent   = "Share this code with agents when they register. It links them to your team automatically.";
    // Update all "office" sub-labels to "team"
    document.querySelectorAll(".office-stat-sub").forEach(el => {
      el.textContent = el.textContent.replace("your office", "your team").replace("all agents", "all members");
    });
  } else {
    if (panelTitle) panelTitle.textContent = "Office Dashboard";
    if (panelSub)   panelSub.textContent   = "Your agents, their content activity, and compliance — all in one place.";
    if (codeLabel)  codeLabel.textContent  = "Your Office Code";
    if (codeHint)   codeHint.textContent   = "Share this code with agents when they register. It links them to your office automatically.";
    document.querySelectorAll(".office-stat-sub").forEach(el => {
      el.textContent = el.textContent.replace("your team", "your office").replace("all members", "all agents");
    });
  }

  // Fetch join code
  const codeEndpoint = isTeam
    ? `${BACKEND_URL}/auth/team/team-code`
    : `${BACKEND_URL}/auth/broker/office-code`;
  if (user?.role === "broker" || user?.role === "team" || user?.role === "super_admin" || user?.role === "admin") {
    try {
      const res = await authFetch(codeEndpoint);
      if (res.ok) {
        const data    = await res.json();
        const codeEl  = el("broker-office-code");
        const codeVal = data.office_code || data.team_code || "——";
        if (codeEl) codeEl.textContent = codeVal;
      }
    } catch(e) {}
  }

  const wrap = el("broker-agent-table-wrap"); if (!wrap) return;
  try {
    const endpoint = isTeam ? `${BACKEND_URL}/team/stats` : `${BACKEND_URL}/broker/office-stats`;
    const res = await authFetch(endpoint);
    if (!res.ok) throw new Error("Failed");
    renderBrokerOffice((await res.json()).agents||[]);
  } catch(e) {
    if (wrap) wrap.innerHTML = '<div style="padding:24px;color:var(--muted);">Could not load data. Please refresh.</div>';
  }
}
function relativeTime(iso) {
  if (!iso) return "—";
  try {
    const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
    if (diff < 60)          return "just now";
    if (diff < 3600)        return Math.floor(diff/60) + "m ago";
    if (diff < 86400)       return Math.floor(diff/3600) + "h ago";
    if (diff < 86400*30)    return Math.floor(diff/86400) + "d ago";
    return new Date(iso).toLocaleDateString("en-US",{month:"short",day:"numeric"});
  } catch(e) { return "—"; }
}

function complianceColor(rate) {
  if (rate === null || rate === undefined) return "var(--muted)";
  if (rate >= 90) return "var(--green)";
  if (rate >= 70) return "var(--amber)";
  return "var(--red)";
}

function statusBadge(status) {
  const cfg = {
    active:   { bg:"var(--green-dim,rgba(26,127,75,0.08))",   color:"var(--green)",  label:"Active"   },
    inactive: { bg:"var(--amber-dim,rgba(138,79,0,0.08))",    color:"var(--amber)",  label:"Inactive" },
    new:      { bg:"rgba(23,73,201,0.07)",                    color:"var(--blue)",   label:"New"      },
  };
  const s = cfg[status] || cfg.new;
  return `<span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:4px;background:${s.bg};color:${s.color};">${s.label}</span>`;
}

function renderBrokerOffice(agents) {
  const totalPending   = agents.reduce((s,a) => s + (a.pending  || 0), 0);
  const totalPublished = agents.reduce((s,a) => s + (a.published|| 0), 0);
  const rates          = agents.filter(a => a.compliance_rate !== null && a.compliance_rate !== undefined);
  const avgComp        = rates.length ? Math.round(rates.reduce((s,a) => s + a.compliance_rate, 0) / rates.length) : null;

  set("broker-stat-agents",     agents.length);
  set("broker-stat-pending",    totalPending);
  set("broker-stat-published",  totalPublished);
  set("broker-stat-compliance", avgComp !== null ? `${avgComp}%` : "—");

  const wrap = el("broker-agent-table-wrap");
  if (!wrap) return;
  if (!agents.length) {
    wrap.innerHTML = '<div style="padding:24px;color:var(--muted);">No agents linked to your office yet. Share your office code or send an invite above.</div>';
    return;
  }

  const headers = ["Agent", "Score", "Published", "Compliance", "Last Active", "Status", "Actions"];
  const headerHTML = headers.map(h =>
    `<th style="text-align:left;padding:10px 12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:var(--muted);white-space:nowrap;">${h}</th>`
  ).join("");

  const rowsHTML = agents.map(a => {
    const scoreColor = a.score >= 75 ? "var(--green)" : a.score >= 40 ? "var(--amber)" : "var(--red)";
    return `
      <tr id="broker-agent-row-${a.id}" style="border-bottom:1px solid var(--border);cursor:pointer;" onclick="toggleAgentDrilldown(${a.id})">
        <td style="padding:10px 12px;">
          <div style="font-weight:600;">${a.name || a.agent_name || "—"}</div>
          <div style="font-size:11px;color:var(--muted);">${a.email || ""}</div>
          ${a.has_schedule ? '<div style="font-size:10px;color:var(--teal,#0d9488);margin-top:2px;">⏱ Scheduled</div>' : ""}
        </td>
        <td style="padding:10px 12px;font-weight:700;color:${scoreColor};">${a.score ?? "—"}</td>
        <td style="padding:10px 12px;">${a.published ?? 0}
          ${a.pending ? `<span style="font-size:11px;color:var(--amber);margin-left:4px;">(${a.pending} pending)</span>` : ""}
        </td>
        <td style="padding:10px 12px;font-weight:600;color:${complianceColor(a.compliance_rate)};">
          ${a.compliance_rate !== null && a.compliance_rate !== undefined ? a.compliance_rate + "%" : "—"}
        </td>
        <td style="padding:10px 12px;font-size:12px;color:var(--muted);">${relativeTime(a.last_activity)}</td>
        <td style="padding:10px 12px;">${statusBadge(a.status)}</td>
        <td style="padding:10px 12px;">
          <div style="display:flex;gap:8px;align-items:center;">
            <a href="#" onclick="event.preventDefault();event.stopPropagation();generateAgentComplianceReport(String(${a.id}),'${(a.name||a.agent_name||"").replace(/'/g,"\\'")}','${(a.email||"").replace(/'/g,"\\'")}');"
               style="font-size:11px;font-weight:600;color:var(--blue);text-decoration:none;">Report</a>
            <a href="#" onclick="event.preventDefault();event.stopPropagation();toggleAgentDrilldown(${a.id});"
               style="font-size:11px;font-weight:600;color:var(--ink-3);text-decoration:none;" id="broker-view-btn-${a.id}">▸ Content</a>
          </div>
        </td>
      </tr>
      <tr id="broker-drilldown-${a.id}" style="display:none;">
        <td colspan="7" style="padding:0;background:var(--surface,#fafaf8);border-bottom:2px solid var(--border);">
          <div id="broker-drilldown-content-${a.id}" style="padding:16px 20px;">
            <div style="color:var(--muted);font-size:13px;">Loading…</div>
          </div>
        </td>
      </tr>`;
  }).join("");

  wrap.innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="border-bottom:2px solid var(--border);">${headerHTML}</tr></thead>
      <tbody>${rowsHTML}</tbody>
    </table>`;
}

async function toggleAgentDrilldown(agentId) {
  const row     = el(`broker-drilldown-${agentId}`);
  const content = el(`broker-drilldown-content-${agentId}`);
  const btn     = el(`broker-view-btn-${agentId}`);
  if (!row || !content) return;

  const isOpen = row.style.display !== "none";
  if (isOpen) {
    row.style.display = "none";
    if (btn) btn.textContent = "▸ Content";
    return;
  }

  row.style.display = "table-row";
  if (btn) btn.textContent = "▾ Content";

  // Only fetch if not already loaded
  if (content.dataset.loaded === "true") return;
  content.innerHTML = '<div style="color:var(--muted);font-size:13px;">Loading content…</div>';

  try {
    const res   = await authFetch(`${BACKEND_URL}/broker/agent-content?agent_id=${agentId}&limit=15`);
    if (!res.ok) throw new Error("Failed");
    const data  = await res.json();
    const items = data.items || [];
    content.dataset.loaded = "true";

    if (!items.length) {
      content.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:8px 0;">No content yet for this agent.</div>';
      return;
    }

    const compBadge = (c) => {
      const cfg = {
        pass:      { color:"var(--green)", label:"✓ Pass"    },
        review:    { color:"var(--amber)", label:"⚠ Review"  },
        attention: { color:"var(--red)",   label:"✗ Attention"},
        pending:   { color:"var(--muted)", label:"— Pending" },
      };
      const s = cfg[c] || cfg.pending;
      return `<span style="font-size:11px;font-weight:600;color:${s.color};">${s.label}</span>`;
    };

    const statusBadgeSmall = (s) => {
      const colors = { published:"var(--blue)", approved:"var(--green)", pending:"var(--amber)" };
      return `<span style="font-size:10px;font-weight:600;text-transform:uppercase;color:${colors[s]||"var(--muted)"};">${s}</span>`;
    };

    const rows = items.map(item => `
      <tr style="border-bottom:1px solid var(--border);">
        <td style="padding:8px 10px;max-width:280px;">
          <div style="font-weight:600;font-size:12px;line-height:1.4;">${item.headline || "—"}</div>
          ${item.cir_id ? `<div style="font-size:10px;color:var(--blue);margin-top:2px;">CIR™ ${item.cir_id}</div>` : ""}
        </td>
        <td style="padding:8px 10px;font-size:11px;color:var(--muted);white-space:nowrap;">${item.niche || "—"}</td>
        <td style="padding:8px 10px;">${statusBadgeSmall(item.status)}</td>
        <td style="padding:8px 10px;">${compBadge(item.compliance)}</td>
        <td style="padding:8px 10px;font-size:11px;color:var(--muted);white-space:nowrap;">
          ${item.platforms.length ? item.platforms.join(", ") : "Not posted"}
        </td>
        <td style="padding:8px 10px;font-size:11px;color:var(--muted);white-space:nowrap;">
          ${relativeTime(item.approved_at || item.saved_at)}
        </td>
      </tr>`).join("");

    content.innerHTML = `
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:10px;">
        Recent Content — ${items.length} item${items.length!==1?"s":""}
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead>
          <tr style="border-bottom:1px solid var(--border);">
            ${["Headline","Niche","Status","Compliance","Platforms","Date"].map(h =>
              `<th style="text-align:left;padding:6px 10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);">${h}</th>`
            ).join("")}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch(e) {
    content.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:8px 0;">Could not load content. Please try again.</div>';
  }
}
// ─────────────────────────────────────────────
// INVITE AGENT — Bug #6 fix: wire button + send email via /office/invite
// ─────────────────────────────────────────────
el("invite-agent-btn")?.addEventListener("click", async () => {
  const name  = el("invite-agent-name")?.value.trim()  || "";
  const email = el("invite-agent-email")?.value.trim() || "";
  const phone = el("invite-agent-phone")?.value.trim() || "";
  const msg   = el("invite-agent-msg");

  if (!name || !email) {
    if (msg) { msg.textContent = "⚠ Please enter the agent's name and email."; msg.style.color = "var(--red)"; msg.style.display = "block"; }
    return;
  }

  const btn = el("invite-agent-btn");
  btn.disabled = true; btn.textContent = "Sending…";

  try {
    const res  = await authFetch(`${BACKEND_URL}/office/invite`, {
      method: "POST",
      body:   JSON.stringify({ name, email, phone }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Invite failed");
    if (msg) { msg.textContent = `✓ Invite sent to ${name} (${email}).`; msg.style.color = "var(--green)"; msg.style.display = "block"; }
    // Clear fields on success
    if (el("invite-agent-name"))  el("invite-agent-name").value  = "";
    if (el("invite-agent-email")) el("invite-agent-email").value = "";
    if (el("invite-agent-phone")) el("invite-agent-phone").value = "";
    setTimeout(() => { if (msg) msg.style.display = "none"; }, 4000);
  } catch(err) {
    if (msg) { msg.textContent = `⚠ ${err.message}`; msg.style.color = "var(--red)"; msg.style.display = "block"; }
  } finally {
    btn.disabled = false; btn.textContent = "Send Invite";
  }
});

// This replaces the broken generateAgentComplianceReport function
// Written directly as JS to avoid Python escape issues

async function generateAgentComplianceReport(agentId, agentName, agentEmail) {
  var isDemo = localStorage.getItem("hb_demo_mode") === "true";
  var date   = new Date().toLocaleDateString("en-US",{year:"numeric",month:"long",day:"numeric"});

  if (isDemo) {
    var lib    = window._demoLibrary || [];
    var passed = lib.filter(function(x) { var v = (x.compliance && (x.compliance.overall_verdict||x.compliance.overallStatus)) || ""; return v==="pass"||v==="compliant"; }).length;
    var total  = lib.length;

    var rows = lib.map(function(x) {
      var verdict = (x.compliance && (x.compliance.overall_verdict||x.compliance.overallStatus)) || "review";
      var isPass  = verdict==="pass"||verdict==="compliant";
      var notes   = (x.compliance && x.compliance.notes) || [];
      var actionNotes = notes.filter(function(n){ return n && !n.toLowerCase().includes("state rules:") && !n.toLowerCase().includes("jurisdiction") && !n.toLowerCase().includes("mls reminder"); });
      var notesHtml = "";
      if (!isPass && actionNotes.length) {
        notesHtml = actionNotes.map(function(n){
          var m = n.match(/^\[([^\]]+)\]\s*(.+)$/);
          if (m) return "<div style='font-size:11px;color:#b45309;margin-top:4px;'>⚠ " + m[1] + ": " + m[2].replace(/\s*\(triggered:[^)]+\)/,"").trim() + "</div>";
          return "<div style='font-size:11px;color:#b45309;margin-top:4px;'>⚠ " + n + "</div>";
        }).join("");
      }
      return "<tr style='border-bottom:1px solid #e5e7eb;'>" +
        "<td style='padding:10px 12px;font-size:13px;'>" + (x.content && x.content.headline ? x.content.headline : "Untitled") + notesHtml + "</td>" +
        "<td style='padding:10px 12px;font-size:13px;text-transform:capitalize;'>" + (x.niche||"—") + "</td>" +
        "<td style='padding:10px 12px;font-size:13px;text-transform:capitalize;'>" + (x.status||"pending") + "</td>" +
        "<td style='padding:10px 12px;font-size:13px;font-weight:600;color:" + (isPass?"#16a34a":"#b45309") + ";'>" + (isPass?"✓ Pass":"⚠ Review") + "</td>" +
        "</tr>";
    }).join("");

    var compRate = total > 0 ? Math.round((passed/total)*100) : 100;
    var compColor = compRate >= 90 ? "#15803d" : compRate >= 70 ? "#b45309" : "#b91c1c";

    var toolbar = "<div style='position:sticky;top:0;z-index:100;background:#1d1d1f;padding:12px 48px;display:flex;align-items:center;justify-content:space-between;'>" +
      "<span style='font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(255,255,255,0.6);'>PaperTrail\u2122 \u00b7 " + agentName + "</span>" +
      "<div style='display:flex;gap:8px;'>" +
      "<button onclick='window.print()' style='padding:8px 20px;border-radius:999px;font-size:13px;font-weight:500;cursor:pointer;font-family:inherit;border:none;background:#fff;color:#1d1d1f;'>\u2b07 Download PDF</button>" +
      "<button onclick='window.close()' style='padding:8px 20px;border-radius:999px;font-size:13px;font-weight:500;cursor:pointer;font-family:inherit;border:1px solid rgba(255,255,255,0.25);background:transparent;color:rgba(255,255,255,0.7);'>Close \u2715</button>" +
      "</div></div>";

    var html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>PaperTrail\u2122 \u2014 " + agentName + "</title>" +
      "<style>@media print{.no-print{display:none!important;}}body{font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;color:#1d1d1f;margin:0;padding:0;background:#fff;}" +
      ".page{max-width:860px;margin:0 auto;padding:60px 48px;}" +
      ".header{border-bottom:2px solid #1d1d1f;padding-bottom:24px;margin-bottom:40px;}" +
      ".logo{font-size:13px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#1d1d1f;margin-bottom:4px;}" +
      ".rtitle{font-size:32px;font-weight:700;letter-spacing:-0.04em;margin:0 0 8px;}" +
      ".stitle{font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#6b7280;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #e5e7eb;margin-top:40px;}" +
      "table{width:100%;border-collapse:collapse;}th{text-align:left;padding:8px 12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6b7280;border-bottom:2px solid #e5e7eb;}" +
      ".footer{margin-top:60px;padding-top:24px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;}</style></head>" +
      "<body><div class='no-print'>" + toolbar + "</div><div class='page'>" +
      "<div class='header'><div class='logo'>HomeBridge \u00b7 PaperTrail\u2122</div><div class='rtitle'>Agent Compliance Report</div>" +
      "<div style='font-size:13px;color:#6b7280;'>" + agentName + " \u00b7 " + agentEmail + " \u00b7 Generated " + date + "</div></div>" +
      "<div style='display:flex;gap:40px;margin-bottom:40px;'>" +
      "<div><div style='font-size:40px;font-weight:700;letter-spacing:-0.04em;'>" + total + "</div><div style='font-size:12px;color:#6b7280;margin-top:4px;'>Total Content</div></div>" +
      "<div><div style='font-size:40px;font-weight:700;letter-spacing:-0.04em;'>" + passed + "</div><div style='font-size:12px;color:#6b7280;margin-top:4px;'>Passed Review</div></div>" +
      "<div><div style='font-size:40px;font-weight:700;letter-spacing:-0.04em;color:" + compColor + ";'>" + compRate + "%</div><div style='font-size:12px;color:#6b7280;margin-top:4px;'>Compliance Rate</div></div>" +
      "</div><div class='stitle'>Content Audit Record</div>" +
      "<table><thead><tr><th>Headline</th><th>Niche</th><th>Status</th><th>Compliance</th></tr></thead><tbody>" + rows + "</tbody></table>" +
      "<div class='footer'>Generated by HomeBridge PaperTrail\u2122 \u00b7 For internal compliance review only \u00b7 Not legal advice \u00b7 homebridgegroup.co</div>" +
      "</div></body></html>";

    var blob = new Blob([html], { type:"text/html" });
    var url  = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(function(){ URL.revokeObjectURL(url); }, 5000);
    return;
  }

  // Real: call backend
  try {
    var res = await authFetch(BACKEND_URL + "/broker/agent-compliance-report", {
      method:"POST", body:JSON.stringify({ agent_id: agentId })
    });
    if (!res.ok) throw new Error("Failed");
    var blob = await res.blob();
    var url  = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(function(){ URL.revokeObjectURL(url); }, 5000);
  } catch(e) { showToast("Could not generate report for " + agentName + ". Please try again."); }
}

function loadDemoBrokerView() {
  const demoAgents = [
    { name:"Brooke Callahan", email:"brooke@callahan-properties.com", score:67, pending:2, published:3, compliance_rate:100, status:"active" },
    { name:"James Whitfield",  email:"j.whitfield@callahan-properties.com", score:55, pending:1, published:4, compliance_rate:100, status:"active" },
    { name:"Dana Solis",       email:"d.solis@callahan-properties.com", score:38, pending:0, published:1, compliance_rate:72, status:"warning" },
    { name:"Marcus Obi",       email:"m.obi@callahan-properties.com", score:44, pending:3, published:2, compliance_rate:88, status:"active" },
    { name:"Lynn Patterson",   email:"l.patterson@callahan-properties.com", score:29, pending:0, published:0, compliance_rate:null, status:"pending" },
  ];
  renderBrokerOffice(demoAgents);
}

// ─────────────────────────────────────────────
// SECTION 31: ADMIN DASHBOARD
// ─────────────────────────────────────────────
async function loadAdminDashboard() {
  showAdminSection("dashboard");
  _wireAdminButtons();
  _wireCreateUserForm();
}

function _wireAdminButtons() {
  const createBtn   = el("demo-generate-btn");
  const refreshBtn  = el("admin-refresh-btn");
  const previewBtn  = el("admin-preview-demo-btn");
  const searchInput = el("admin-search");

  if (createBtn) {
    const newBtn = createBtn.cloneNode(true);
    createBtn.parentNode.replaceChild(newBtn, createBtn);
    newBtn.addEventListener("click", async () => {
      const label = el("demo-label-input")?.value.trim() || "Demo Link";
      newBtn.disabled = true; newBtn.textContent = "Creating…";
      try {
        const res = await authFetch(`${BACKEND_URL}/demo/create-token`, {
          method: "POST", body: JSON.stringify({ label })
        });
        if (!res.ok) throw new Error("Failed");
        const inp = el("demo-label-input");
        if (inp) inp.value = "";
        loadDemoTokens();
      } catch(e) {
        alert("Could not create demo link. Please try again.");
      } finally {
        newBtn.disabled = false; newBtn.textContent = "Create Demo Link";
      }
    });
  }

  if (refreshBtn) {
    const newRef = refreshBtn.cloneNode(true);
    refreshBtn.parentNode.replaceChild(newRef, refreshBtn);
    newRef.addEventListener("click", loadAdminDashboard);
  }

  if (previewBtn) {
    const newPrev = previewBtn.cloneNode(true);
    previewBtn.parentNode.replaceChild(newPrev, previewBtn);
    newPrev.addEventListener("click", () => {
      window.open(window.location.pathname + "?demo=preview", "_blank");
    });
  }

  if (searchInput) {
    const newSearch = searchInput.cloneNode(true);
    searchInput.parentNode.replaceChild(newSearch, searchInput);
    newSearch.addEventListener("input", renderAdminUsers);
  }
}

function _wireCreateUserForm() {
  const form = el("create-user-form");
  if (!form) return;
  const newForm = form.cloneNode(true);
  form.parentNode.replaceChild(newForm, form);
  newForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn        = newForm.querySelector("#create-user-btn");
    const email      = newForm.querySelector("#cu-email")?.value.trim();
    const password   = newForm.querySelector("#cu-password")?.value.trim();
    const agentName  = newForm.querySelector("#cu-name")?.value.trim();
    const brokerage  = newForm.querySelector("#cu-brokerage")?.value.trim() || "";
    const role       = newForm.querySelector("#cu-role")?.value || "agent";
    const isLicensed = newForm.querySelector("#cu-licensed")?.checked ? 1 : 0;
    const isInsider  = newForm.querySelector("#cu-insider")?.checked ? true : false;
    const plan       = isInsider ? "insider" : "trial";
    if (!email || !password || !agentName) { showToast("Email, password, and name are required."); return; }
    btn.textContent = "Creating…"; btn.disabled = true;
    try {
      const res = await authFetch(`${BACKEND_URL}/admin/create-user`, {
        method: "POST",
        body: JSON.stringify({ email, password, agent_name: agentName, brokerage, role, is_licensed: isLicensed, plan })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Failed");
      showToast(`✓ Account created — ${agentName} (${role})`);
      newForm.reset();
    } catch(e) {
      showToast("Could not create user — " + e.message);
    } finally {
      btn.textContent = "Create Account"; btn.disabled = false;
    }
  });
}

async function loadAuditLog() {
  const content = el("audit-log-content");
  if (!content) return;
  content.innerHTML = '<div style="padding:16px;color:var(--muted);">Loading…</div>';
  try {
    const res = await authFetch(`${BACKEND_URL}/support/audit-log`);
    if (!res.ok) throw new Error("Failed");
    const data = await res.json();
    const logs = data.logs || [];
    if (!logs.length) { content.innerHTML = '<div style="padding:24px;color:var(--muted);">No audit events yet.</div>'; return; }
    content.innerHTML = `<table class="admin-user-table">
      <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead>
      <tbody>${logs.map(l => `<tr>
        <td style="font-size:11px;color:var(--muted);">${(l.created_at||"").slice(0,16).replace("T"," ")}</td>
        <td style="font-size:12px;">${l.actor_id||"—"}</td>
        <td style="font-size:12px;font-weight:600;">${l.action||"—"}</td>
        <td style="font-size:12px;">${l.target_id||"—"}</td>
        <td style="font-size:12px;color:var(--muted);">${(l.detail||"").slice(0,80)||"—"}</td>
      </tr>`).join("")}</tbody>
    </table>`;
  } catch(e) {
    content.innerHTML = '<div style="padding:24px;color:var(--muted);">Could not load audit log.</div>';
  }
}

// ─────────────────────────────────────────────
// COMPLIANCE ADMIN
// ─────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════
// COMPLIANCE CHECKER — Four-zone dashboard
// Zone 1: Command strip stats
// Zone 2: Attention required (overdue rules)
// Zone 3: 12-layer framework accordion
// Zone 4: Review history
// ══════════════════════════════════════════════════════════════════

// 12-layer static framework definition — mirrors compliance_rules_meta.json layers block
const COMPLIANCE_LAYERS = {
  "1":  { name:"Fair Housing Act",                   status:"built",   authority:"42 U.S.C. § 3604(c) / HUD 24 C.F.R. § 100.75" },
  "2":  { name:"Civil Rights Act",                   status:"partial", authority:"42 U.S.C. § 1982 / Civil Rights Act 1866" },
  "3":  { name:"ADA Accessibility",                  status:"planned", authority:"42 U.S.C. § 12101 / WCAG 2.1" },
  "4":  { name:"State Commission Advertising Rules",  status:"built",   authority:"State real estate commission regulations" },
  "5":  { name:"RESPA",                               status:"built",   authority:"12 U.S.C. § 2607 / CFPB 12 C.F.R. Part 1024" },
  "6":  { name:"FTC Advertising Rules",               status:"partial", authority:"15 U.S.C. § 45 / FTC 16 C.F.R. Part 255" },
  "7":  { name:"State Deceptive Trade Practices",     status:"planned", authority:"CO C.R.S. § 6-1-105 / TX DTPA / CA UCL and equivalents" },
  "8":  { name:"Copyright / IP Law",                  status:"planned", authority:"17 U.S.C. / MLS listing data ownership rules" },
  "9":  { name:"MLS Rules",                           status:"partial", authority:"NAR MLS Policy Statement 7.58 / local MLS rules" },
  "10": { name:"Platform Ad Rules",                   status:"planned", authority:"Meta Special Ad Categories / Google Ads Housing Policy" },
  "11": { name:"FinCEN",                              status:"monitor", authority:"Bank Secrecy Act / FinCEN GTOs / 2024 Proposed Rulemaking" },
  "12": { name:"AI-Generated Content Compliance",     status:"partial", authority:"FTC AI Guidance 2023-2024 / CA AB 2602 / NAR AI Guidelines" },
};

const LAYER_STATUS_CONFIG = {
  built:   { label:"Active",       bg:"var(--green-dim)",              color:"var(--green)",  desc:"Checks run on every post" },
  partial: { label:"In Progress",  bg:"#fffbeb",                       color:"#b45309",       desc:"Core rules active — expanded coverage in development" },
  planned: { label:"Scheduled",    bg:"var(--bg-sunken)",              color:"var(--ink-4)",  desc:"Defined scope — not yet active in automated review" },
  monitor: { label:"Monitoring",   bg:"var(--blue-dim)",               color:"var(--blue)",   desc:"Low current applicability — tracked for changes" },
};

async function loadComplianceStatus() {
  const layerListEl  = el("comp-layer-list");
  const historyEl    = el("comp-history-list");
  if (!layerListEl) return;

  layerListEl.innerHTML = '<div style="font-size:13px;color:var(--ink-3);padding:16px 0;">Loading…</div>';
  if (historyEl) historyEl.innerHTML = '<div style="font-size:13px;color:var(--ink-3);padding:16px;">Loading history…</div>';

  try {
    const res = await authFetch(`${BACKEND_URL}/admin/compliance/status`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const federal  = data.federal || [];
    const states   = data.states  || [];
    const history  = data.review_history  || [];
    const normalizedFederal = federal.map(r => ({
      ...r,
      name: r.name || r.source || r.key,
      days_since_verified: (r.days_since_verified != null) ? r.days_since_verified : (r.days_since_verification != null ? r.days_since_verification : null),
    }));
    const normalizedStates = states.map(r => ({
      ...r,
      name: r.name || r.label || r.state,
      days_since_verified: (r.days_since_verified != null) ? r.days_since_verified : (r.days_since_verification != null ? r.days_since_verification : null),
    }));
    const allRules = [...normalizedFederal, ...normalizedStates];

    // Rules version
    const versionEl = el("comp-rules-version");
    if (versionEl) versionEl.textContent = data.rules_version || "—";

    // ── Zone 1: Command strip ──
    _compRenderCommandStrip(allRules, data);

    // ── Zone 2: Attention required ──
    _compRenderAttentionZone(allRules);

    // ── Zone 3: 12-layer framework ──
    _compRenderLayerFramework(allRules);

    // ── Zone 4: Review history ──
    _compRenderHistory(history, allRules);

  } catch(e) {
    if (layerListEl) layerListEl.innerHTML = `<div style="font-size:13px;color:var(--red);padding:16px 0;">Could not load compliance status — ${e.message}</div>`;
  }
}

function _compRenderCommandStrip(allRules, meta) {
  // Layers current = built/partial layers where ALL their rules are current (not overdue)
  // Needs attention = any rule that is overdue or never verified
  // Coverage gaps = layers that are partial or planned
  const overdueRules = allRules.filter(r => r.overdue || r.days_since_verified === null);
  const gapLayers    = Object.values(COMPLIANCE_LAYERS).filter(l => l.status === "partial" || l.status === "planned").length;

  // Count layers that have at least one rule AND all rules current
  const layerNums    = Object.keys(COMPLIANCE_LAYERS);
  let currentLayers  = 0;
  layerNums.forEach(num => {
    const layerRules = allRules.filter(r => String(r.layer) === String(num));
    if (layerRules.length > 0 && layerRules.every(r => !r.overdue && r.days_since_verified !== null)) currentLayers++;
  });

  const set = (id, val) => { const e = el(id); if (e) e.textContent = val; };
  set("comp-stat-current",   currentLayers);
  set("comp-stat-attention", overdueRules.length);
  set("comp-stat-gaps",      gapLayers);

  // Next review due — find earliest next_review date across all rules
  const upcoming = allRules
    .filter(r => r.next_review)
    .sort((a,b) => a.next_review.localeCompare(b.next_review));
  const nextEl      = el("comp-stat-next");
  const nextLabelEl = el("comp-stat-next-label");
  if (upcoming.length && nextEl) {
    nextEl.textContent      = upcoming[0].next_review;
    if (nextLabelEl) nextLabelEl.textContent = upcoming[0].name || upcoming[0].key || "—";
  } else {
    if (nextEl)      nextEl.textContent      = "—";
    if (nextLabelEl) nextLabelEl.textContent = "No scheduled reviews";
  }
}

function _compRenderAttentionZone(allRules) {
  const attZone   = el("comp-attention-zone");
  const attList   = el("comp-attention-list");
  const clearZone = el("comp-allclear-zone");

  const overdue = allRules.filter(r => r.overdue || r.days_since_verified === null);

  if (!attZone || !clearZone) return;

  if (overdue.length === 0) {
    attZone.style.display   = "none";
    clearZone.style.display = "block";
    return;
  }

  attZone.style.display   = "block";
  clearZone.style.display = "none";

  if (!attList) return;
  attList.innerHTML = overdue.map(r => {
    const never    = r.days_since_verified === null;
    const urgency  = never ? "Never reviewed" : `${r.days_since_verified}d overdue`;
    const urgencyColor = never ? "var(--red)" : "var(--red)";
    const layerNum = r.layer || "—";
    const layerName = COMPLIANCE_LAYERS[String(layerNum)]?.name || "";
    return `<div style="display:flex;align-items:flex-start;gap:12px;padding:12px 14px;border:1px solid rgba(185,28,28,0.2);border-radius:10px;background:var(--red-dim);">
      <div style="flex:1;min-width:0;">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:2px;">
          <span style="font-size:10px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;color:var(--ink-4);">Layer ${layerNum}</span>
          <span style="font-size:13px;font-weight:700;color:var(--ink);">${r.name || r.key}</span>
          <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:999px;background:var(--red);color:#fff;">${urgency}</span>
        </div>
        <div style="font-size:11px;color:var(--ink-3);">${r.citation || ""}</div>
        ${r.next_review ? `<div style="font-size:11px;color:var(--red);margin-top:2px;">Review due: ${r.next_review}</div>` : ""}
      </div>
      <button class="btn-secondary" style="font-size:11px;padding:5px 12px;white-space:nowrap;flex-shrink:0;border-color:var(--red);color:var(--red);"
        onclick="openComplianceModal('${r.key}','${(r.name||r.key).replace(/'/g,"\\'")}','${layerNum}','${layerName.replace(/'/g,"\\'")}')">
        Record Review
      </button>
    </div>`;
  }).join("");
}

function _compRenderLayerFramework(allRules) {
  const listEl = el("comp-layer-list");
  if (!listEl) return;

  listEl.innerHTML = Object.entries(COMPLIANCE_LAYERS).map(([num, layer]) => {
    const cfg        = LAYER_STATUS_CONFIG[layer.status] || LAYER_STATUS_CONFIG.planned;
    const layerRules = allRules.filter(r => String(r.layer) === String(num));
    const hasRules   = layerRules.length > 0;
    const anyOverdue = layerRules.some(r => r.overdue || r.days_since_verified === null);

    // Last verified — most recent across all rules in this layer
    const verified = layerRules
      .filter(r => r.verified_date)
      .sort((a,b) => b.verified_date.localeCompare(a.verified_date));
    const lastVerified = verified.length ? verified[0].verified_date : null;

    // Next review — earliest across all rules in this layer
    const upcoming = layerRules
      .filter(r => r.next_review)
      .sort((a,b) => a.next_review.localeCompare(b.next_review));
    const nextReview = upcoming.length ? upcoming[0].next_review : null;

    const alertDot = anyOverdue ? `<div style="width:7px;height:7px;border-radius:50%;background:var(--red);flex-shrink:0;margin-top:6px;"></div>` : "";

    const rulesHtml = hasRules ? layerRules.map(r => _compSubRow(r, num)).join("") :
      `<div style="padding:10px 14px;font-size:12px;color:var(--ink-4);font-style:italic;">No rules built yet for this layer. ${layer.status === 'planned' ? 'Planned for future build.' : layer.status === 'monitor' ? 'Monitoring only — low current applicability.' : ''}</div>`;

    return `<div style="border:1px solid var(--border);border-radius:var(--radius-md);overflow:hidden;background:var(--white);">
      <!-- Layer header row — clickable accordion -->
      <div style="display:flex;align-items:center;gap:12px;padding:13px 16px;cursor:pointer;user-select:none;transition:background 0.12s;"
           onclick="_compToggleLayer(this)"
           onmouseenter="this.style.background='var(--bg-sunken)'"
           onmouseleave="this.style.background=''">
        ${alertDot}
        <div style="width:28px;height:28px;border-radius:6px;background:${cfg.bg};border:1px solid ${cfg.color}33;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <span style="font-size:11px;font-weight:800;color:${cfg.color};">${num}</span>
        </div>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span style="font-size:13px;font-weight:700;color:var(--ink);">${layer.name}</span>
            <span style="font-size:10px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;padding:2px 8px;border-radius:999px;background:${cfg.bg};color:${cfg.color};">${cfg.label}</span>
            ${anyOverdue ? '<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:999px;background:var(--red);color:#fff;">Overdue</span>' : ""}
          </div>
          <div style="font-size:11px;color:var(--ink-4);margin-top:2px;">${layer.authority}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;margin-right:8px;">
          ${lastVerified ? `<div style="font-size:11px;font-weight:600;color:var(--ink-3);">Verified ${lastVerified}</div>` : `<div style="font-size:11px;color:var(--ink-4);">Not yet verified</div>`}
          ${nextReview ? `<div style="font-size:10px;color:var(--ink-4);margin-top:1px;">Next: ${nextReview}</div>` : ""}
        </div>
        <div style="font-size:14px;color:var(--ink-4);flex-shrink:0;transition:transform 0.2s;" class="comp-layer-arrow">›</div>
      </div>
      <!-- Layer rules — hidden by default -->
      <div style="display:none;border-top:1px solid var(--border);background:var(--bg-sunken);" class="comp-layer-body">
        <div style="padding:4px 0;">${rulesHtml}</div>
      </div>
    </div>`;
  }).join("");
}

function _compToggleLayer(headerEl) {
  const body  = headerEl.nextElementSibling;
  const arrow = headerEl.querySelector(".comp-layer-arrow");
  const open  = body.style.display !== "none";
  body.style.display  = open ? "none" : "block";
  if (arrow) arrow.style.transform = open ? "" : "rotate(90deg)";
}

function _compSubRow(r, layerNum) {
  const days    = r.days_since_verified;
  const overdue = r.overdue;
  const never   = days === null;
  const soon    = r.due_soon && !overdue;

  const statusBg    = overdue || never ? "var(--red-dim)"   : soon ? "#fffbeb"        : "var(--green-dim)";
  const statusColor = overdue || never ? "var(--red)"        : soon ? "#b45309"        : "var(--green)";
  const statusLabel = overdue           ? "Overdue"           : never ? "Never verified" : soon ? "Due soon" : "Current";
  const daysLabel   = never ? "" : `${days}d ago`;
  const verifiedBy  = r.verified_by ? ` · ${r.verified_by}` : "";
  const nextStr     = r.next_review ? `Next: ${r.next_review}` : "";
  const layerName   = COMPLIANCE_LAYERS[String(layerNum)]?.name || "";
  const stagedBadge = r.status === "staged" ? `<span style="font-size:10px;padding:2px 7px;border-radius:999px;background:var(--bg);color:var(--ink-4);font-weight:600;border:1px solid var(--border);">Staged</span>` : "";

  return `<div style="display:flex;align-items:flex-start;gap:12px;padding:11px 16px;border-bottom:1px solid var(--border);background:var(--white);">
    <div style="flex:1;min-width:0;">
      <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:2px;">
        <span style="font-size:13px;font-weight:600;color:var(--ink);">${r.name || r.key}</span>
        <span style="font-size:10px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;padding:2px 7px;border-radius:999px;background:${statusBg};color:${statusColor};">${statusLabel}</span>
        ${stagedBadge}
      </div>
      <div style="font-size:11px;color:var(--ink-4);margin-bottom:2px;">${r.citation || ""}</div>
      <div style="font-size:11px;color:var(--ink-3);">${daysLabel}${verifiedBy}${nextStr ? " · " + nextStr : ""}</div>
      ${r.review_notes ? `<div style="font-size:11px;color:var(--ink-3);margin-top:3px;font-style:italic;">${r.review_notes}</div>` : ""}
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0;">
      <button class="btn-secondary" style="font-size:11px;padding:4px 11px;white-space:nowrap;"
        onclick="openComplianceModal('${r.key}','${(r.name||r.key).replace(/'/g,"\\'")}','${layerNum}','${layerName.replace(/'/g,"\\'")}')">
        Record Review
      </button>
      ${r.source_url ? `<a href="${r.source_url}" target="_blank" rel="noopener" style="font-size:10px;color:var(--blue);text-decoration:none;white-space:nowrap;">View source ↗</a>` : ""}
    </div>
  </div>`;
}

function _compRenderHistory(history, allRules) {
  const historyEl = el("comp-history-list");
  if (!historyEl) return;

  // If backend returns history, use it. Otherwise synthesise from rule verified_by/verified_date fields.
  let entries = [];
  if (history && history.length) {
    entries = history;
  } else {
    // Synthesise from rules that have been verified
    entries = allRules
      .filter(r => r.verified_date && r.verified_by)
      .sort((a,b) => b.verified_date.localeCompare(a.verified_date))
      .map(r => ({
        date:     r.verified_date,
        rule:     r.name || r.key,
        layer:    r.layer,
        reviewer: r.verified_by,
        notes:    r.review_notes || "",
      }));
  }

  if (!entries.length) {
    historyEl.innerHTML = '<div style="font-size:13px;color:var(--ink-3);padding:20px;">No review history recorded yet.</div>';
    return;
  }

  historyEl.innerHTML = entries.map((h, i) => {
    const layerName = COMPLIANCE_LAYERS[String(h.layer)]?.name || "";
    const border    = i < entries.length - 1 ? "border-bottom:1px solid var(--border);" : "";
    return `<div style="display:flex;align-items:flex-start;gap:14px;padding:12px 16px;${border}">
      <div style="flex-shrink:0;text-align:right;min-width:72px;">
        <div style="font-size:12px;font-weight:600;color:var(--ink-3);">${h.date || "—"}</div>
      </div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:13px;font-weight:600;color:var(--ink);">${h.rule || "—"}</div>
        ${h.layer ? `<div style="font-size:11px;color:var(--ink-4);margin-top:1px;">Layer ${h.layer}${layerName ? " · " + layerName : ""}</div>` : ""}
        ${h.notes ? `<div style="font-size:12px;color:var(--ink-3);margin-top:3px;font-style:italic;">${h.notes}</div>` : ""}
      </div>
      <div style="flex-shrink:0;font-size:12px;color:var(--ink-3);white-space:nowrap;">
        ${h.reviewer || ""}
      </div>
    </div>`;
  }).join("");
}

function openComplianceModal(key, name, layerNum, layerName) {
  const modal = el("comp-review-modal");
  if (!modal) return;

  // Header
  const layerLabelEl = el("comp-modal-layer-label");
  if (layerLabelEl) layerLabelEl.textContent = layerNum ? `Layer ${layerNum} — ${layerName || ""}` : "Compliance Checker";
  el("comp-modal-title").textContent    = name || "Record Review";
  el("comp-modal-subtitle").textContent = "Confirm you have verified this rule set against its primary source.";

  // Fields
  el("comp-modal-source-key").value = key;
  el("comp-reviewer-name").value    = "";
  el("comp-review-notes").value     = "";
  el("comp-review-url").value       = "";

  // Reset checkboxes
  ["comp-check-text","comp-check-citations","comp-check-guidance","comp-check-url"].forEach(id => {
    const cb = el(id);
    if (cb) cb.checked = (id === "comp-check-text" || id === "comp-check-citations");
  });

  // Reset error
  const errEl = el("comp-modal-error");
  if (errEl) { errEl.style.display = "none"; errEl.textContent = ""; }

  modal.style.display = "flex";
}

function closeComplianceModal() {
  const modal = el("comp-review-modal");
  if (modal) modal.style.display = "none";
}

async function submitComplianceReview() {
  const key      = (el("comp-modal-source-key")?.value || "").trim();
  const reviewer = (el("comp-reviewer-name")?.value    || "").trim();
  const notes    = (el("comp-review-notes")?.value     || "").trim();
  const url      = (el("comp-review-url")?.value       || "").trim();
  const errEl    = el("comp-modal-error");

  // Collect checked verifications
  const verified = [];
  if (el("comp-check-text")?.checked)      verified.push("rule_text");
  if (el("comp-check-citations")?.checked) verified.push("citations");
  if (el("comp-check-guidance")?.checked)  verified.push("no_new_guidance");
  if (el("comp-check-url")?.checked)       verified.push("source_url");

  if (!reviewer) {
    if (errEl) { errEl.textContent = "Reviewer name is required."; errEl.style.display = "block"; }
    return;
  }

  const btn = document.querySelector("#comp-review-modal .btn-primary");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  try {
    const res = await authFetch(`${BACKEND_URL}/admin/compliance/verify-state`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ source_key: key, verified_by: reviewer, notes, source_url: url, verified_items: verified }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    closeComplianceModal();
    await loadComplianceStatus();
  } catch(e) {
    if (errEl) { errEl.textContent = `Error: ${e.message}`; errEl.style.display = "block"; }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Record Review"; }
  }
}

async function loadAdminStats() {
  try {
    const res = await authFetch(`${BACKEND_URL}/admin/stats`);
    if (!res.ok) return;
    const s = await res.json();
    set("adm-total-users",    s.total_users    ?? "—");
    set("adm-new-users",      `${s.new_users_30d ?? "—"} new this month`);
    set("adm-brokers-agents", `${s.total_brokers ?? "—"} / ${s.total_agents ?? "—"}`);
    set("adm-total-content",  s.total_content  ?? "—");
    set("adm-content-week",   `${s.content_this_week ?? "—"} pieces this week`);
    set("adm-published",      s.total_published ?? "—");
    set("adm-schedules",      `${s.active_schedules ?? "—"} active schedules`);
  } catch(e) { console.error("Admin stats error:", e); }
}

async function loadAdminUsers() {
  const wrap = el("admin-user-table-wrap");
  try {
    const [usersRes, partnersRes] = await Promise.all([
      authFetch(`${BACKEND_URL}/admin/users`),
      authFetch(`${BACKEND_URL}/admin/partners`),
    ]);
    if (!usersRes.ok) throw new Error("Failed");
    _adminUsers = (await usersRes.json()).users || [];
    // Build partner lookup keyed by user_id — silently ignore if endpoint fails
    if (partnersRes.ok) {
      const pData = await partnersRes.json();
      _adminPartners = {};
      (pData.partners || []).forEach(p => { _adminPartners[String(p.user_id)] = p; });
    }
    renderAdminUsers();
  } catch(e) {
    if (wrap) wrap.innerHTML = `<div class="office-empty">Could not load users. Please refresh.</div>`;
  }
}

function renderAdminUsers() {
  const wrap   = el("admin-user-table-wrap");
  const search = (el("admin-search")?.value || "").toLowerCase();
  if (!wrap) return;

  let users = _adminUsers;
  const hbUser = JSON.parse(localStorage.getItem("hb_user") || "null");

  if (_adminRoleFilter === "inactive") {
    users = users.filter(u => !u.is_active);
  } else if (_adminRoleFilter !== "all") {
    users = users.filter(u => (u.role || "agent") === _adminRoleFilter);
  }
  if (search) {
    users = users.filter(u =>
      (u.agent_name || "").toLowerCase().includes(search) ||
      (u.email      || "").toLowerCase().includes(search) ||
      (u.brokerage  || "").toLowerCase().includes(search)
    );
  }

  if (!users.length) { wrap.innerHTML = `<div class="office-empty">No users match this filter.</div>`; return; }

  const rows = users.map(u => {
    const role        = u.role || "agent";
    const active      = u.is_active;
    const joined      = (u.created_at || "").slice(0,10);
    const roleLabels = {
      super_admin:  "⭐ Super Admin",
      admin:        "⚙ Admin",
      support:      "⊙ Support",
      broker:       "⌂ Office",
      agent:        "Agent",
      coach:        "◈ Coach",
      assistant:    "Assistant",
      hb_marketer:  "◈ Mktg Staff",
      team:         "◈ Team",
    };
    const planLabels = {
      trial:          "Trial",
      insider:        "⭐ Insider",
      founding_member:"Founding",
      starter:        "Starter",
      professional:   "Pro",
      power:          "Power",
      coach:          "Coach",
    };
    const plan        = u.plan || "trial";
    const roleDisplay = roleLabels[role] || role;
    const planDisplay = planLabels[plan] || plan;
    const roleHTML    = `<span class="role-badge role-${role}">${roleDisplay}</span>`;
    const planHTML    = `<span style="font-size:11px;color:${plan==="insider"?"var(--gold)":"var(--ink-3)"};">${planDisplay}</span>`;
    const statusHTML  = active
      ? `<span class="status-dot dot-active"></span>Active`
      : `<span class="status-dot dot-inactive"></span>Inactive`;
    // Partner badge — shown if this user is enrolled in the partner program
    const partner = _adminPartners[String(u.id)];
    const partnerHTML = partner ? (() => {
      const tierColors = { elite:"var(--gold)", broker:"var(--blue)", referral:"var(--green)" };
      const tierLabels = { elite:"Elite", broker:"Growth", referral:"Starter" };
      const tColor = tierColors[partner.tier] || "var(--ink-3)";
      const tLabel = tierLabels[partner.tier] || partner.tier || "Partner";
      const isSuspended = partner.status === "suspended";
      return `<div style="margin-top:4px;display:flex;align-items:center;gap:5px;flex-wrap:wrap;">
        <span style="font-size:10px;font-weight:700;padding:2px 6px;border-radius:4px;
          background:${isSuspended?"var(--red-dim, rgba(185,28,28,0.1))":"rgba(0,0,0,0.05)"};
          color:${isSuspended?"var(--red)":tColor};white-space:nowrap;">
          ♦ ${isSuspended ? "Suspended" : tLabel}
        </span>
        <span style="font-size:10px;font-family:monospace;color:var(--ink-4);letter-spacing:0.05em;">
          ${partner.referral_code || ""}
        </span>
        ${partner.total_referred ? `<span style="font-size:10px;color:var(--ink-4);">${partner.total_referred} ref${partner.total_referred!==1?"s":""}</span>` : ""}
      </div>`;
    })() : "";
    const isMe = String(u.id) === String(hbUser?.id);
    return `<tr>
      <td><div style="font-weight:600;color:var(--ink);">${u.agent_name||"—"}</div><div style="font-size:11px;color:var(--muted);">${u.email}</div></td>
      <td>${u.brokerage||"—"}</td>
      <td>${roleHTML} ${planHTML}${partnerHTML}</td>
      <td style="text-align:center;">${u.content_count??0}</td>
      <td style="font-size:12px;color:var(--muted);">${joined}</td>
      <td style="font-size:12px;">${statusHTML}</td>
      <td><div style="display:flex;gap:6px;flex-wrap:wrap;">
        ${String(u.id) === String(hbUser?.id) || u.role === "super_admin"
          ? `<span style="font-size:11px;color:var(--muted);padding:3px 6px;">${u.role === "super_admin" ? "⭐ Super Admin" : "You"}</span>`
          : `<select class="admin-role-select btn-secondary" data-uid="${u.id}" style="font-size:11px;padding:3px 8px;cursor:pointer;">
          <option value="agent"       ${role==="agent"       ?"selected":""}>Agent</option>
          <option value="coach"       ${role==="coach"       ?"selected":""}>Coach</option>
          <option value="assistant"   ${role==="assistant"   ?"selected":""}>Assistant</option>
          <option value="broker"      ${role==="broker"      ?"selected":""}>Office / Broker</option>
          <option value="hb_marketer" ${role==="hb_marketer" ?"selected":""}>Marketing Staff</option>
          <option value="support"     ${role==="support"     ?"selected":""}>Support</option>
          <option value="admin"       ${role==="admin"       ?"selected":""}>Admin</option>
        </select>
        <select class="admin-plan-select btn-secondary" data-uid="${u.id}" style="font-size:11px;padding:3px 8px;cursor:pointer;${plan==="insider"?"color:var(--gold);font-weight:600;":""}">
          <option value="trial"           ${plan==="trial"           ?"selected":""}>Trial</option>
          <option value="insider"         ${plan==="insider"         ?"selected":""}>⭐ Insider</option>
          <option value="founding_member" ${plan==="founding_member" ?"selected":""}>Founding Member</option>
          <option value="starter"         ${plan==="starter"         ?"selected":""}>Starter</option>
          <option value="professional"    ${plan==="professional"    ?"selected":""}>Professional</option>
          <option value="power"           ${plan==="power"           ?"selected":""}>Power</option>
          <option value="coach"           ${plan==="coach"           ?"selected":""}>Coach</option>
        </select>`}
        ${!isMe ? `<button class="btn-secondary admin-toggle-active" data-uid="${u.id}" data-active="${active}" style="font-size:11px;padding:3px 10px;color:${active?"var(--red)":"var(--green)"};">${active?"Disable":"Enable"}</button>` : `<span style="font-size:11px;color:var(--muted);padding:3px 6px;">You</span>`}
        ${!isMe ? `<button class="btn-secondary admin-delete-user" data-uid="${u.id}" data-name="${(u.agent_name||"").replace(/"/g,"")}" style="font-size:11px;padding:3px 10px;color:var(--muted);">Delete</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");

  wrap.innerHTML = `<table class="admin-user-table">
    <thead><tr>
      <th>User</th><th>Brokerage</th><th>Role</th>
      <th style="text-align:center;">Content</th><th>Joined</th><th>Status</th><th>Actions</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;

  // Wire role selects
  wrap.querySelectorAll(".admin-role-select").forEach(sel => {
    sel.addEventListener("change", async () => {
      const uid = sel.dataset.uid; const role = sel.value;
      try {
        const res = await authFetch(`${BACKEND_URL}/admin/set-role`, { method:"POST", body:JSON.stringify({ user_id:parseInt(uid), role }) });
        if (!res.ok) throw new Error("Failed");
        const u = _adminUsers.find(x=>String(x.id)===String(uid)); if (u) u.role = role;
        renderAdminUsers();
      } catch(e) { showToast("Could not update role — please try again."); await loadAdminUsers(); }
    });
  });

  // Wire plan selects
  wrap.querySelectorAll(".admin-plan-select").forEach(sel => {
    sel.addEventListener("change", async () => {
      const uid = sel.dataset.uid; const plan = sel.value;
      try {
        const res = await authFetch(`${BACKEND_URL}/admin/set-plan`, { method:"POST", body:JSON.stringify({ user_id:parseInt(uid), plan }) });
        if (!res.ok) throw new Error("Failed");
        const u = _adminUsers.find(x=>String(x.id)===String(uid)); if (u) u.plan = plan;
        showToast(`✓ Plan updated to ${plan}`);
        renderAdminUsers();
      } catch(e) { showToast("Could not update plan — please try again."); await loadAdminUsers(); }
    });
  });

  // Wire enable/disable
  wrap.querySelectorAll(".admin-toggle-active").forEach(btn => {
    btn.addEventListener("click", async () => {
      const uid = btn.dataset.uid; const active = btn.dataset.active === "true";
      if (active) {
        const u = _adminUsers.find(x=>String(x.id)===String(uid));
        if (!confirm(`Disable ${u?.agent_name||"this user"}?\n\nThey will be locked out immediately.\n\nClick OK to confirm.`)) return;
      }
      btn.textContent = "…"; btn.disabled = true;
      try {
        const res = await authFetch(`${BACKEND_URL}/admin/set-active`, { method:"POST", body:JSON.stringify({ user_id:parseInt(uid), is_active:!active }) });
        if (!res.ok) throw new Error("Failed");
        const u = _adminUsers.find(x=>String(x.id)===String(uid)); if (u) u.is_active = !active;
        renderAdminUsers();
      } catch(e) { showToast("Could not update account status — please try again."); btn.textContent = active?"Disable":"Enable"; btn.disabled = false; }
    });
  });

  // Wire delete
  wrap.querySelectorAll(".admin-delete-user").forEach(btn => {
    btn.addEventListener("click", async () => {
      const uid = btn.dataset.uid; const name = btn.dataset.name || "this user";
      if (!confirm(`Permanently delete ${name}?\n\nAll their content and data will be removed.\n\nClick OK to confirm.`)) return;
      if (!confirm(`Second confirmation required.\n\nDeleting ${name} is permanent and irreversible. Continue?`)) return;
      btn.textContent = "Deleting…"; btn.disabled = true;
      try {
        const res = await authFetch(`${BACKEND_URL}/admin/delete-user`, { method:"POST", body:JSON.stringify({ user_id:parseInt(uid) }) });
        if (!res.ok) { const err=await res.json().catch(()=>({})); throw new Error(err.detail||"Failed"); }
        _adminUsers = _adminUsers.filter(x=>String(x.id)!==String(uid));
        renderAdminUsers();
      } catch(e) { showToast("Could not delete user — " + e.message); btn.textContent="Delete"; btn.disabled=false; }
    });
  });
}

// Role filter wiring (data-role-filter buttons are always in DOM)
document.querySelectorAll("[data-role-filter]").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("[data-role-filter]").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    _adminRoleFilter = btn.dataset.roleFilter;
    renderAdminUsers();
  });
});

function loadDemoTokens() {
  const wrap = el("demo-token-list"); if (!wrap) return;
  authFetch(`${BACKEND_URL}/demo/tokens`).then(async res => {
    if (!res.ok) throw new Error("Failed");
    const data = await res.json();
    renderDemoLinks(data.tokens || []);
  }).catch(() => { if (wrap) wrap.innerHTML = '<div style="color:var(--muted);">Could not load demo links.</div>'; });
}
function renderDemoLinks(tokens) {
  const wrap = el("demo-token-list"); if (!wrap) return;
  if (!tokens.length) { wrap.innerHTML = '<div style="color:var(--muted);font-size:13px;">No demo links yet. Create one below.</div>'; return; }
  wrap.innerHTML = tokens.map(t => {
    const url = `${window.location.origin}/index.html?demo=${t.token}`;
    return `<div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:8px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
      <div style="flex:1;"><div style="font-size:13px;font-weight:600;">${t.label||"Demo Link"}</div><div style="font-size:11px;color:var(--muted);margin-top:3px;">${url}</div></div>
      <button onclick="navigator.clipboard.writeText('${url}').then(()=>{this.textContent='Copied!';setTimeout(()=>this.textContent='Copy Link',1500)})" style="font-size:12px;padding:6px 14px;background:var(--blue);color:#fff;border:none;border-radius:8px;cursor:pointer;">Copy Link</button>
      <button onclick="adminDeleteDemoLink('${t.id}')" style="font-size:12px;padding:6px 14px;background:transparent;color:var(--red,#b91c1c);border:1px solid var(--red,#b91c1c);border-radius:8px;cursor:pointer;">Delete</button>
    </div>`;
  }).join("");
}
async function adminDeleteDemoLink(id) {
  if (!confirm("Delete this demo link?")) return;
  try { await authFetch(`${BACKEND_URL}/demo/tokens/${id}`, { method:"DELETE" }); loadAdminDashboard(); }
  catch(e) {}
}
// create-link-btn and refresh-btn are wired inside _wireAdminButtons()

// ─────────────────────────────────────────────
// SECTION 32: BILLING
// ─────────────────────────────────────────────
async function loadBillingStatus() {
  const container = el("billing-section"); if (!container) return;
  if (localStorage.getItem("hb_demo_mode") === "true") {
    const badge = el("billing-status-badge");
    const hint  = el("billing-status-hint");
    if (badge) { badge.textContent = "Demo mode"; badge.style.background = "var(--bg)"; badge.style.color = "var(--ink-3)"; }
    if (hint)  hint.textContent = "Billing is not available in demo mode.";
    const trialBlock = el("billing-trial-block");
    const activeBlock = el("billing-active-block");
    if (trialBlock) trialBlock.style.display = "none";
    if (activeBlock) activeBlock.style.display = "none";
    return;
  }
  try {
    const res = await authFetch(`${BACKEND_URL}/billing/status`);
    if (!res.ok) return;
    const data = await res.json();

    const badge       = el("billing-status-badge");
    const hint        = el("billing-status-hint");
    const trialBlock  = el("billing-trial-block");
    const activeBlock = el("billing-active-block");
    const pendingBlock = el("billing-pending-block");

    // Hide all blocks first
    if (trialBlock)   trialBlock.style.display  = "none";
    if (activeBlock)  activeBlock.style.display  = "none";
    if (pendingBlock) pendingBlock.style.display = "none";

    if (data.status === "active") {
      // Active paid subscription
      const planLabel = (data.plan || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
      if (badge) { badge.textContent = `Active — ${planLabel}`; badge.style.background = "#f0fdf4"; badge.style.color = "#166534"; }
      if (hint)  hint.textContent = `Your ${planLabel} plan is active.`;
      if (activeBlock) activeBlock.style.display = "block";
    } else {
      // Trial or expired — show plan picker
      const isExpired = data.status === "expired";
      if (badge) { badge.textContent = isExpired ? "Trial ended" : "Free trial"; badge.style.background = isExpired ? "#fff7ed" : "var(--blue-dim,#eef2ff)"; badge.style.color = isExpired ? "#c2410c" : "var(--blue)"; }
      if (hint)  hint.textContent = isExpired
        ? "Your trial has ended. Subscribe below to continue."
        : `Trial: ${data.days_left ?? 0} days left. Subscribe below to unlock full access.`;
      if (trialBlock) trialBlock.style.display = "block";
    }
  } catch(e) {}
}

// Wire plan-select buttons → Stripe Checkout
document.addEventListener("click", async function(e) {
  const btn = e.target.closest(".plan-select-btn");
  if (!btn) return;
  const priceKey = btn.getAttribute("data-price-key");
  if (!priceKey) return;
  btn.disabled = true;
  btn.textContent = "Redirecting…";
  try {
    const res = await authFetch(`${BACKEND_URL}/billing/create-checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ price_key: priceKey })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || "Billing error — please try again.");
      btn.disabled = false;
      btn.textContent = "Subscribe";
      return;
    }
    const data = await res.json();
    if (data.checkout_url) {
      window.location = data.checkout_url;
    } else {
      showToast("Could not start checkout — please try again.");
      btn.disabled = false;
      btn.textContent = "Subscribe";
    }
  } catch(err) {
    showToast("Network error — please try again.");
    btn.disabled = false;
    btn.textContent = "Subscribe";
  }
});

// Wire billing portal button
el("billing-portal-btn")?.addEventListener("click", async function() {
  this.disabled = true;
  this.textContent = "Opening…";
  try {
    const res = await authFetch(`${BACKEND_URL}/billing/portal`, { method: "POST" });
    if (!res.ok) { showToast("Could not open billing portal."); this.disabled = false; this.textContent = "Manage Billing & Invoices →"; return; }
    const data = await res.json();
    if (data.portal_url) window.open(data.portal_url, "_blank");
  } catch(e) { showToast("Network error."); }
  this.disabled = false;
  this.textContent = "Manage Billing & Invoices →";
});

// ─────────────────────────────────────────────
// SECTION 33: FILM MODAL (TELEPROMPTER)
// ─────────────────────────────────────────────
function openFilmModal(item) {
  currentFilmItem = item;
  const modal = el("film-modal"); if (!modal) return;
  modal.style.display = "flex";
  const titleEl = el("film-modal-title"); if (titleEl) titleEl.textContent = item.content?.headline || "Film This";
  const scriptEl = el("teleprompter-text"); if (scriptEl) { scriptEl.textContent = item.content?.script || "No script available."; scriptEl.scrollTop = 0; }
  const platformEl = el("platform-reminder"); if (platformEl) platformEl.textContent = item.platform ? `Platform: ${item.platform}` : "";
  const recBtn = el("record-btn"); if (recBtn) { recBtn.disabled=true; recBtn.style.opacity="0.4"; }
  el("stop-btn") && (el("stop-btn").style.display = "none");
  el("camera-placeholder") && (el("camera-placeholder").style.display = "flex");
}
function closeFilmModal() {
  if (filmRecorder?.state === "recording") filmRecorder.stop();
  if (filmStream) { filmStream.getTracks().forEach(t=>t.stop()); filmStream = null; }
  if (filmTimer) { clearInterval(filmTimer); filmTimer = null; }
  stopAutoScroll();
  const modal = el("film-modal"); if (modal) modal.style.display = "none";
  const preview = el("camera-preview"); if (preview) preview.srcObject = null;
  const ph = el("camera-placeholder"); if (ph) ph.style.display = "flex";
}
async function startCamera() {
  if (filmStream) { filmStream.getTracks().forEach(t=>t.stop()); }
  try {
    filmStream = await navigator.mediaDevices.getUserMedia({ video:{ facingMode:currentFacingMode }, audio:true });
    const preview = el("camera-preview"); if (preview) { preview.srcObject=filmStream; preview.style.display="block"; }
    const ph = el("camera-placeholder"); if (ph) ph.style.display="none";
    const recBtn = el("record-btn"); if (recBtn) { recBtn.disabled=false; recBtn.style.opacity="1"; }
    const flipBtn = el("flip-camera-btn"); if (flipBtn) flipBtn.style.display="inline-block";
  } catch(e) { showToast("Camera access denied or unavailable. Check your browser permissions."); }
}
function updateTimerDisplay(secs) {
  const m = Math.floor(secs/60), s = secs%60;
  const str = `${m}:${s.toString().padStart(2,"0")}`;
  const timerEl = el("rec-timer"); if (timerEl) timerEl.textContent = str;
  const overlayEl = el("rec-timer-overlay"); if (overlayEl) overlayEl.textContent = str;
}
function startRecording() {
  if (!filmStream) return;
  filmChunks = [];
  const mimeTypes = ["video/webm;codecs=vp9,opus","video/webm;codecs=vp8,opus","video/webm","video/mp4"];
  let mimeType = ""; for (const mt of mimeTypes) { if (MediaRecorder.isTypeSupported(mt)) { mimeType=mt; break; } }
  filmRecorder = new MediaRecorder(filmStream, mimeType?{mimeType}:{});
  filmRecorder.ondataavailable = e => { if (e.data.size>0) filmChunks.push(e.data); };
  filmRecorder.onstop = () => saveRecording();
  filmRecorder.start(100);
  el("record-btn") && (el("record-btn").style.display="none");
  el("stop-btn")   && (el("stop-btn").style.display="inline-block");
  const ov = el("recording-overlay"); if (ov) ov.style.display="flex";
  filmSeconds=0; filmTimer=setInterval(()=>{filmSeconds++;updateTimerDisplay(filmSeconds);},1000);
  if (autoScrollActive) startAutoScroll();
}
function stopRecording() {
  if (filmRecorder?.state!=="inactive") filmRecorder.stop();
  if (filmTimer) { clearInterval(filmTimer); filmTimer=null; }
  stopAutoScroll();
  el("record-btn") && Object.assign(el("record-btn").style,{display:"inline-block",opacity:"0.4"});
  el("record-btn") && (el("record-btn").disabled=true);
  el("stop-btn")   && (el("stop-btn").style.display="none");
  const ov = el("recording-overlay"); if (ov) ov.style.display="none";
}
function saveRecording() {
  if (!filmChunks.length) return;
  const ext  = filmChunks[0]?.type?.includes("mp4")?"mp4":"webm";
  const blob = new Blob(filmChunks, { type:filmChunks[0]?.type||"video/webm" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  const title = (currentFilmItem?.content?.headline||"homebridge-video").replace(/[^a-z0-9]+/gi,"-").toLowerCase().slice(0,40);
  a.href=url; a.download=`${title}.${ext}`; a.click(); URL.revokeObjectURL(url);
  const notice = el("video-saved-notice"); if (notice) { notice.style.display="block"; setTimeout(()=>notice.style.display="none",3500); }
  if (currentFilmItem?.id) apiPatchLibraryItem(currentFilmItem.id, { videoRecordedAt:new Date().toISOString(), videoRecordedSeconds:filmSeconds }).catch(()=>{});
  const recBtn = el("record-btn"); if (recBtn) { recBtn.disabled=false; recBtn.style.opacity="1"; }
}
function startAutoScroll() {
  stopAutoScroll();
  const textEl = el("teleprompter-text"); const speed = parseInt(el("scroll-speed")?.value||"3");
  if (!textEl||speed===0) return;
  autoScrollTimer = setInterval(()=>{textEl.scrollTop+=speed*0.4;},50);
}
function stopAutoScroll() { if (autoScrollTimer){clearInterval(autoScrollTimer);autoScrollTimer=null;} }

el("camera-start-btn")?.addEventListener("click", startCamera);
el("record-btn")?.addEventListener("click", startRecording);
el("stop-btn")?.addEventListener("click", stopRecording);
el("film-modal-close")?.addEventListener("click", closeFilmModal);
el("flip-camera-btn")?.addEventListener("click", async ()=>{ currentFacingMode=currentFacingMode==="user"?"environment":"user"; await startCamera(); });
el("auto-scroll-toggle")?.addEventListener("click", function(){ autoScrollActive=!autoScrollActive; this.textContent=autoScrollActive?"Auto-scroll: ON":"Auto-scroll: OFF"; this.style.background=autoScrollActive?"#1749c9":"rgba(255,255,255,0.08)"; this.style.color=autoScrollActive?"#fff":"rgba(255,255,255,0.6)"; if (autoScrollActive&&filmRecorder?.state==="recording") startAutoScroll(); else stopAutoScroll(); });
el("scroll-speed")?.addEventListener("input",()=>{ if (autoScrollActive&&filmRecorder?.state==="recording") startAutoScroll(); });

// ─────────────────────────────────────────────
// SECTION 34: COMPLIANCE REPORT
// ─────────────────────────────────────────────
el("compliance-report-btn")?.addEventListener("click", async () => {
  const btn = el("compliance-report-btn");
  btn.disabled = true; btn.textContent = "Loading…";
  const saved  = getSaved();
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";

  // ── Build the history modal ──────────────────────────────────────────────
  function _verdictBadge(status) {
    const map = {
      "reviewed":           ["#f0fdf4","#15803d","✓ Reviewed"],
      "review-recommended": ["#fffbeb","#b45309","⚠ Review"],
      "attention-required": ["#fef2f2","#b91c1c","✗ Attention"],
      "pass":               ["#f0fdf4","#15803d","✓ Reviewed"],
      "warn":               ["#fffbeb","#b45309","⚠ Review"],
      "fail":               ["#fef2f2","#b91c1c","✗ Attention"],
    };
    const [bg,color,label] = map[status] || ["#f8f7f5","#7a7470","—"];
    return `<span style="font-size:11px;font-weight:700;padding:2px 10px;border-radius:4px;background:${bg};color:${color};">${label}</span>`;
  }

  function _buildHistoryModal(records) {
    const name = saved.agentName || "Agent";
    const existing = document.getElementById("compliance-history-modal");
    if (existing) existing.remove();
    const modal = document.createElement("div");
    modal.id = "compliance-history-modal";
    modal.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:9999;display:flex;align-items:center;justify-content:center;padding:20px;";

    const rows = records.length ? records.map((r, idx) => {
      const comp   = r.compliance || {};
      const checks = comp.disclosureChecks || comp.notes || [];
      const rv     = comp.rules_version || r.rules_version || "";
      const vdates = comp.rules_verified_dates || {};
      const semantic = comp.semanticAssessment || "";
      const domainRows = [
        ["Fair Housing",        r.fair_housing     || comp.fairHousing     || ""],
        ["Brokerage Disclosure",r.disclosure       || comp.brokerageDisclosure || ""],
        ["NAR Standards",       r.nar_standards    || comp.narStandards    || ""],
        ["State Compliance",    r.state_compliance || comp.stateCompliance || ""],
      ].filter(([,v]) => v).map(([label, verdict]) => {
        const color = verdict === "pass" ? "var(--green)" : verdict === "warn" ? "var(--amber)" : verdict === "fail" ? "var(--red)" : "var(--ink-3)";
        const icon  = verdict === "pass" ? "✓" : verdict === "warn" ? "⚠" : verdict === "fail" ? "✗" : "—";
        return `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);">
          <span style="font-size:11px;color:var(--ink-3);">${label}</span>
          <span style="font-size:11px;font-weight:700;color:${color};">${icon} ${verdict}</span>
        </div>`;
      }).join("");
      const vdateRows = Object.entries(vdates).map(([k,v]) =>
        `<span style="font-size:10px;background:var(--bg-sunken);padding:2px 7px;border-radius:4px;color:var(--ink-3);">${k}: ${v}</span>`
      ).join(" ");
      const checkRows = checks.map(c =>
        `<div style="font-size:11px;color:var(--ink-2);line-height:1.5;padding:3px 0;border-bottom:1px solid var(--border-subtle);">${c}</div>`
      ).join("");
      const detailId = `cir-detail-${idx}`;
      return `
      <div style="border:1px solid var(--border);border-radius:10px;margin-bottom:8px;background:var(--white);overflow:hidden;">
        <div style="padding:14px 16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
            <div style="flex:1;min-width:0;">
              <div style="font-size:12px;color:var(--ink-3);margin-bottom:3px;">${r.niche || "—"} · ${(r.approved_at || "").slice(0,10)}</div>
              <div style="font-size:13px;font-weight:600;color:var(--ink);line-height:1.4;margin-bottom:6px;">${r.headline || "Post"}</div>
              <button data-cir-toggle="${detailId}"
                style="background:none;border:none;padding:0;cursor:pointer;font-family:inherit;display:flex;align-items:center;gap:4px;">
                <span style="font-size:11px;font-weight:700;color:var(--gold);letter-spacing:0.04em;">${r.cir_id || ""}</span>
                <span style="font-size:10px;color:var(--ink-3);">· tap to ${checks.length ? "view checks" : "view detail"} ↕</span>
              </button>
            </div>
            <div style="flex-shrink:0;">${_verdictBadge(r.overall_status)}</div>
          </div>
        </div>
        <div id="${detailId}" style="display:none;border-top:1px solid var(--border);padding:14px 16px;background:var(--bg);">
          ${rv || vdateRows ? `
          <div style="margin-bottom:10px;">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);margin-bottom:5px;">Rules Version</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;">
              ${rv ? `<span style="font-size:10px;background:var(--gold-dim);padding:2px 7px;border-radius:4px;color:var(--gold);font-weight:700;">${rv}</span>` : ""}
              ${vdateRows}
            </div>
          </div>` : ""}
          ${domainRows ? `
          <div style="margin-bottom:10px;">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);margin-bottom:5px;">Domain Verdicts</div>
            ${domainRows}
          </div>` : ""}
          ${checks.length ? `
          <div style="margin-bottom:${semantic ? "10px" : "0"};">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);margin-bottom:5px;">Compliance Checks (${checks.length})</div>
            ${checkRows}
          </div>` : ""}
          ${semantic ? `
          <div>
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);margin-bottom:5px;">Semantic Assessment</div>
            <div style="font-size:11px;color:var(--ink-2);line-height:1.5;">${semantic}</div>
          </div>` : ""}
          ${!checks.length && !domainRows && !rv ? `<div style="font-size:11px;color:var(--ink-3);">Full compliance detail stored in PDF report.</div>` : ""}
        </div>
      </div>`;
    }).join("") : `<div style="padding:24px;color:var(--ink-3);font-size:13px;text-align:center;">No compliance records yet. Records are created automatically each time you approve a post.</div>`;

    modal.innerHTML = `
      <div style="background:var(--bg);border-radius:16px;max-width:680px;width:100%;max-height:85vh;display:flex;flex-direction:column;box-shadow:var(--shadow-modal);">
        <div style="padding:24px 28px 16px;border-bottom:1px solid var(--border);flex-shrink:0;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;">
            <div>
              <div style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px;">AutoMates · CIR™ Compliance History</div>
              <div style="font-size:18px;font-weight:700;color:var(--ink);">${name}</div>
              <div style="font-size:12px;color:var(--ink-3);margin-top:2px;">${records.length} record${records.length !== 1 ? "s" : ""} — permanent audit trail</div>
            </div>
            <button onclick="document.getElementById('compliance-history-modal').remove()"
              style="background:none;border:none;font-size:20px;color:var(--ink-3);cursor:pointer;line-height:1;flex-shrink:0;">✕</button>
          </div>
          <div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap;align-items:center;">
            <input type="date" id="ch-from" style="font-size:12px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--white);color:var(--ink);font-family:inherit;" placeholder="From">
            <input type="date" id="ch-to" style="font-size:12px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:var(--white);color:var(--ink);font-family:inherit;" placeholder="To">
            <button id="ch-filter-btn" onclick="loadComplianceHistory()" style="font-size:12px;padding:6px 14px;border-radius:6px;background:var(--gold);color:#fff;border:none;cursor:pointer;font-family:inherit;font-weight:600;">Search</button>
            <button id="ch-pdf-btn" onclick="downloadComplianceHistoryPDF()" style="font-size:12px;padding:6px 14px;border-radius:6px;background:var(--white);color:var(--ink);border:1px solid var(--border);cursor:pointer;font-family:inherit;font-weight:600;">⬇ Download PDF</button>
          </div>
        </div>
        <div id="compliance-history-list" style="overflow-y:auto;padding:16px 28px;flex:1;">${rows}</div>
      </div>`;
    document.body.appendChild(modal);

    // Wire toggle buttons via event delegation — avoids all inline quote escaping issues
    modal.addEventListener("click", function(e) {
      const btn = e.target.closest("[data-cir-toggle]");
      if (!btn) return;
      const targetId = btn.dataset.cirToggle;
      const panel = document.getElementById(targetId);
      if (panel) panel.style.display = panel.style.display === "none" ? "block" : "none";
    });
  }

  if (isDemo) {
    // Demo — synthesize records from _demoLibrary
    const lib = (window._demoLibrary || []).filter(x => x.status === "approved" || x.status === "published");
    const demoRecords = lib.map(x => ({
      cir_id:       x.cir_id || "CIR-DEMO-000000",
      niche:        x.niche || "—",
      headline:     x.content?.headline || "Post",
      overall_status: x.compliance?.overall_verdict || x.compliance?.overallStatus || "reviewed",
      approved_at:  x.approvedAt || x.savedAt || "",
    }));
    _buildHistoryModal(demoRecords);
    btn.disabled = false; btn.textContent = "Compliance History";
    return;
  }

  try {
    const res = await authFetch(`${BACKEND_URL}/compliance/history`);
    if (!res.ok) throw new Error();
    const data = await res.json();
    _buildHistoryModal(data.records || []);
  } catch(e) {
    showToast("Could not load compliance history — please try again.");
  } finally {
    btn.disabled = false; btn.textContent = "Compliance History";
  }
});

async function loadComplianceHistory() {
  const list  = document.getElementById("compliance-history-list");
  const from  = document.getElementById("ch-from")?.value || "";
  const to    = document.getElementById("ch-to")?.value || "";
  const saved = getSaved();
  if (!list) return;
  list.innerHTML = '<div style="padding:24px;color:var(--ink-3);font-size:13px;">Loading…</div>';
  function _verdictBadge(status) {
    const map = {
      "reviewed":           ["#f0fdf4","#15803d","✓ Reviewed"],
      "review-recommended": ["#fffbeb","#b45309","⚠ Review"],
      "attention-required": ["#fef2f2","#b91c1c","✗ Attention"],
    };
    const [bg,color,label] = map[status] || ["#f8f7f5","#7a7470","—"];
    return `<span style="font-size:11px;font-weight:700;padding:2px 10px;border-radius:4px;background:${bg};color:${color};">${label}</span>`;
  }
  try {
    const params = new URLSearchParams();
    if (from) params.set("date_from", from);
    if (to)   params.set("date_to",   to);
    const res  = await authFetch(`${BACKEND_URL}/compliance/history?${params}`);
    if (!res.ok) throw new Error();
    const data    = await res.json();
    const records = data.records || [];
    list.innerHTML = records.length ? records.map((r, idx) => {
      const comp   = r.compliance || {};
      const checks = comp.disclosureChecks || comp.notes || [];
      const rv     = comp.rules_version || r.rules_version || "";
      const vdates = comp.rules_verified_dates || {};
      const semantic = comp.semanticAssessment || "";
      const domainRows = [
        ["Fair Housing",        r.fair_housing     || comp.fairHousing     || ""],
        ["Brokerage Disclosure",r.disclosure       || comp.brokerageDisclosure || ""],
        ["NAR Standards",       r.nar_standards    || comp.narStandards    || ""],
        ["State Compliance",    r.state_compliance || comp.stateCompliance || ""],
      ].filter(([,v]) => v).map(([label, verdict]) => {
        const color = verdict === "pass" ? "var(--green)" : verdict === "warn" ? "var(--amber)" : verdict === "fail" ? "var(--red)" : "var(--ink-3)";
        const icon  = verdict === "pass" ? "✓" : verdict === "⚠" ? "⚠" : verdict === "fail" ? "✗" : "—";
        return `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);">
          <span style="font-size:11px;color:var(--ink-3);">${label}</span>
          <span style="font-size:11px;font-weight:700;color:${color};">${icon} ${verdict}</span>
        </div>`;
      }).join("");
      const vdateRows = Object.entries(vdates).map(([k,v]) =>
        `<span style="font-size:10px;background:var(--bg-sunken);padding:2px 7px;border-radius:4px;color:var(--ink-3);">${k}: ${v}</span>`
      ).join(" ");
      const checkRows = checks.map(c =>
        `<div style="font-size:11px;color:var(--ink-2);line-height:1.5;padding:3px 0;border-bottom:1px solid var(--border-subtle);">${c}</div>`
      ).join("");
      const detailId = `cir-s-detail-${idx}`;
      return `
      <div style="border:1px solid var(--border);border-radius:10px;margin-bottom:8px;background:var(--white);overflow:hidden;">
        <div style="padding:14px 16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
            <div style="flex:1;min-width:0;">
              <div style="font-size:12px;color:var(--ink-3);margin-bottom:3px;">${r.niche || "—"} · ${(r.approved_at || "").slice(0,10)}</div>
              <div style="font-size:13px;font-weight:600;color:var(--ink);line-height:1.4;margin-bottom:6px;">${r.headline || "Post"}</div>
              <button data-cir-toggle="${detailId}"
                style="background:none;border:none;padding:0;cursor:pointer;font-family:inherit;display:flex;align-items:center;gap:4px;">
                <span style="font-size:11px;font-weight:700;color:var(--gold);letter-spacing:0.04em;">${r.cir_id || ""}</span>
                <span style="font-size:10px;color:var(--ink-3);">· tap to ${checks.length ? "view checks" : "view detail"} ↕</span>
              </button>
            </div>
            <div style="flex-shrink:0;">${_verdictBadge(r.overall_status)}</div>
          </div>
        </div>
        <div id="${detailId}" style="display:none;border-top:1px solid var(--border);padding:14px 16px;background:var(--bg);">
          ${rv || vdateRows ? `
          <div style="margin-bottom:10px;">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);margin-bottom:5px;">Rules Version</div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;">
              ${rv ? `<span style="font-size:10px;background:var(--gold-dim);padding:2px 7px;border-radius:4px;color:var(--gold);font-weight:700;">${rv}</span>` : ""}
              ${vdateRows}
            </div>
          </div>` : ""}
          ${domainRows ? `
          <div style="margin-bottom:10px;">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);margin-bottom:5px;">Domain Verdicts</div>
            ${domainRows}
          </div>` : ""}
          ${checks.length ? `
          <div>
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);margin-bottom:5px;">Compliance Checks (${checks.length})</div>
            ${checkRows}
          </div>` : ""}
          ${semantic ? `
          <div style="margin-top:10px;">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ink-3);margin-bottom:5px;">Semantic Assessment</div>
            <div style="font-size:11px;color:var(--ink-2);line-height:1.5;">${semantic}</div>
          </div>` : ""}
        </div>
      </div>`;
    }).join("")
    : `<div style="padding:24px;color:var(--ink-3);font-size:13px;text-align:center;">No records found for this date range.</div>`;

    // Wire toggle via event delegation — avoids all inline onclick quoting issues
    list.onclick = function(e) {
      const btn = e.target.closest("[data-cir-toggle]");
      if (!btn) return;
      const panel = document.getElementById(btn.dataset.cirToggle);
      if (panel) panel.style.display = panel.style.display === "none" ? "block" : "none";
    };
  } catch(e) {
    list.innerHTML = '<div style="padding:24px;color:var(--red);font-size:13px;">Could not load records — please try again.</div>';
  }
}

async function downloadComplianceHistoryPDF() {
  const btn  = document.getElementById("ch-pdf-btn");
  const from = document.getElementById("ch-from")?.value || "";
  const to   = document.getElementById("ch-to")?.value   || "";
  if (btn) { btn.disabled = true; btn.textContent = "Generating…"; }
  try {
    const params = new URLSearchParams();
    if (from) params.set("date_from", from);
    if (to)   params.set("date_to",   to);
    const res = await authFetch(`${BACKEND_URL}/compliance/history/report?${params}`);
    if (!res.ok) throw new Error();
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch(e) {
    showToast("PDF generation failed — please try again.");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "⬇ Download PDF"; }
  }
}

// ─────────────────────────────────────────────
// SECTION 35: GLOBAL HELPERS (called from HTML onclick)
// ─────────────────────────────────────────────
let _profileFromGS = false;
function gsGoTo(panel, step) {
  window._gsCurrentStep = step;
  if (panel === "profile-panel") { _profileMode = "guided"; _profileFromGS = true; }
  navigateTo(panel);
}
function togglePwVis(id, btn) {
  const input = el(id); if (!input) return;
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  btn.textContent = show ? "Hide" : "Show";
}

// ─────────────────────────────────────────────
// SECTION 36: NAV BUTTON WIRING (initial)
// ─────────────────────────────────────────────
document.querySelectorAll(".nav-button").forEach(btn => {
  btn.addEventListener("click", () => navigateTo(btn.getAttribute("data-target")));
});
el("identity-edit-link")?.addEventListener("click", () => navigateTo("setup-panel"));

// Logo — navigate to context home
el("nav-logo")?.addEventListener("click", () => {
  const ctx = getViewContext();
  if (ctx === "super_admin" || ctx === "admin" || ctx === "support") { navigateTo("admin-panel"); return; }
  if (ctx === "office" || ctx === "team" || ctx === "broker") { navigateTo("broker-panel"); return; }
  navigateTo("home-panel");
});


// ─────────────────────────────────────────────
// SECTION 35B: OFFICE & TEAM SETUP RENDERERS
// ─────────────────────────────────────────────

function _loadOfficeSetup() {
  const panel = el("setup-panel");
  if (!panel) return;
  const saved = JSON.parse(localStorage.getItem("hb_office_setup") || "{}");
  panel.innerHTML = `
    <div class="panel-header">
      <div>
        <div class="panel-title">Office Setup</div>
        <div class="panel-subtitle">Your office identity — used for compliance disclosures on agent content.</div>
      </div>
    </div>
    <div class="panel-body" style="max-width:640px;">

      <div class="setup-section" style="margin-bottom:28px;">
        <div class="setup-section-header" style="margin-bottom:16px;">
          <span class="setup-step-number">01</span>
          <div class="setup-section-title">Office Information</div>
        </div>
        <div style="display:grid;gap:14px;">
          <div>
            <label class="setup-label">Office Name</label>
            <input type="text" id="office-name" class="setup-input" placeholder="e.g. Lundy Real Estate Group" value="${saved.officeName||''}" />
          </div>
          <div>
            <label class="setup-label">Brokerage Name</label>
            <input type="text" id="office-brokerage" class="setup-input" placeholder="e.g. eXp Realty" value="${saved.brokerage||''}" />
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
            <div>
              <label class="setup-label">Office Phone</label>
              <input type="tel" id="office-phone" class="setup-input" placeholder="(303) 555-0100" value="${saved.officePhone||''}" />
            </div>
            <div>
              <label class="setup-label">State</label>
              <select id="office-state" class="setup-input">
                <option value="">Select state…</option>
                ${["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"].map(s=>`<option value="${s}"${saved.state===s?" selected":""}>${s}</option>`).join("")}
              </select>
            </div>
          </div>
          <div>
            <label class="setup-label">Office Address</label>
            <input type="text" id="office-address" class="setup-input" placeholder="123 Main St, Denver, CO 80202" value="${saved.officeAddress||''}" />
          </div>
        </div>
      </div>

      <div class="setup-section" style="margin-bottom:28px;">
        <div class="setup-section-header" style="margin-bottom:16px;">
          <span class="setup-step-number">02</span>
          <div class="setup-section-title">Broker of Record</div>
        </div>
        <div style="display:grid;gap:14px;">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
            <div>
              <label class="setup-label">Broker Name</label>
              <input type="text" id="office-broker-name" class="setup-input" placeholder="Full legal name" value="${saved.brokerName||''}" />
            </div>
            <div>
              <label class="setup-label">License Number</label>
              <input type="text" id="office-license" class="setup-input" placeholder="e.g. CO-12345678" value="${saved.licenseNumber||''}" />
            </div>
          </div>
        </div>
      </div>

      <div class="setup-section" style="margin-bottom:28px;">
        <div class="setup-section-header" style="margin-bottom:16px;">
          <span class="setup-step-number">03</span>
          <div class="setup-section-title">Office Disclaimer</div>
        </div>
        <div style="font-size:13px;color:var(--ink-3);margin-bottom:10px;">
          Appended to agent content published under your office. Satisfies state disclosure requirements.
        </div>
        <textarea id="office-disclaimer" class="setup-input" rows="3"
          placeholder="e.g. Licensed in Colorado. All content is for informational purposes only."
          style="resize:vertical;">${saved.officeDisclaimer||''}</textarea>
      </div>

      <button class="btn-primary" id="save-office-setup-btn" style="padding:11px 32px;font-size:14px;">Save Office Setup</button>
      <div id="office-setup-saved-msg" style="display:none;font-size:13px;color:var(--green);margin-top:10px;">✓ Saved</div>
    </div>`;

  el("save-office-setup-btn")?.addEventListener("click", () => {
    const data = {
      officeName:      el("office-name")?.value.trim()        || "",
      brokerage:       el("office-brokerage")?.value.trim()   || "",
      officePhone:     el("office-phone")?.value.trim()       || "",
      state:           el("office-state")?.value              || "",
      officeAddress:   el("office-address")?.value.trim()     || "",
      brokerName:      el("office-broker-name")?.value.trim() || "",
      licenseNumber:   el("office-license")?.value.trim()     || "",
      officeDisclaimer:el("office-disclaimer")?.value.trim()  || "",
    };
    localStorage.setItem("hb_office_setup", JSON.stringify(data));
    authFetch(`${BACKEND_URL}/setup/save`, { method:"POST", body:JSON.stringify({ setup:data, context:"office" }) }).catch(()=>{});
    const msg = el("office-setup-saved-msg");
    if (msg) { msg.style.display = "block"; setTimeout(()=>{ msg.style.display="none"; }, 2500); }
  });
}

function _loadTeamSetup() {
  const panel = el("setup-panel");
  if (!panel) return;
  const saved = JSON.parse(localStorage.getItem("hb_team_setup") || "{}");
  panel.innerHTML = `
    <div class="panel-header">
      <div>
        <div class="panel-title">Team Setup</div>
        <div class="panel-subtitle">Your team identity — used for team-level content and compliance context.</div>
      </div>
    </div>
    <div class="panel-body" style="max-width:640px;">

      <div class="setup-section" style="margin-bottom:28px;">
        <div class="setup-section-header" style="margin-bottom:16px;">
          <span class="setup-step-number">01</span>
          <div class="setup-section-title">Team Information</div>
        </div>
        <div style="display:grid;gap:14px;">
          <div>
            <label class="setup-label">Team Name</label>
            <input type="text" id="team-name" class="setup-input" placeholder="e.g. The Lundy Group" value="${saved.teamName||''}" />
          </div>
          <div>
            <label class="setup-label">Team Lead Name</label>
            <input type="text" id="team-lead-name" class="setup-input" placeholder="Full name" value="${saved.teamLeadName||''}" />
          </div>
          <div>
            <label class="setup-label">Brokerage Affiliation</label>
            <input type="text" id="team-brokerage" class="setup-input" placeholder="e.g. eXp Realty" value="${saved.brokerage||''}" />
          </div>
          <div>
            <label class="setup-label">State</label>
            <select id="team-state" class="setup-input">
              <option value="">Select state…</option>
              ${["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"].map(s=>`<option value="${s}"${saved.state===s?" selected":""}>${s}</option>`).join("")}
            </select>
          </div>
        </div>
      </div>

      <div class="setup-section" style="margin-bottom:28px;">
        <div class="setup-section-header" style="margin-bottom:16px;">
          <span class="setup-step-number">02</span>
          <div class="setup-section-title">Team Positioning</div>
        </div>
        <div style="font-size:13px;color:var(--ink-3);margin-bottom:10px;">
          What does your team specialize in? This shapes team-level content tone and focus.
        </div>
        <textarea id="team-positioning" class="setup-input" rows="3"
          placeholder="e.g. We specialize in helping active adults 55+ find their perfect next chapter in the Denver metro."
          style="resize:vertical;">${saved.teamPositioning||''}</textarea>
      </div>

      <button class="btn-primary" id="save-team-setup-btn" style="padding:11px 32px;font-size:14px;">Save Team Setup</button>
      <div id="team-setup-saved-msg" style="display:none;font-size:13px;color:var(--green);margin-top:10px;">✓ Saved</div>
    </div>`;

  el("save-team-setup-btn")?.addEventListener("click", () => {
    const data = {
      teamName:        el("team-name")?.value.trim()         || "",
      teamLeadName:    el("team-lead-name")?.value.trim()    || "",
      brokerage:       el("team-brokerage")?.value.trim()    || "",
      state:           el("team-state")?.value               || "",
      teamPositioning: el("team-positioning")?.value.trim()  || "",
    };
    localStorage.setItem("hb_team_setup", JSON.stringify(data));
    authFetch(`${BACKEND_URL}/setup/save`, { method:"POST", body:JSON.stringify({ setup:data, context:"team" }) }).catch(()=>{});
    const msg = el("team-setup-saved-msg");
    if (msg) { msg.style.display = "block"; setTimeout(()=>{ msg.style.display="none"; }, 2500); }
  });
}

// ─────────────────────────────────────────────
// SECTION 36: INIT — SINGLE ENTRY POINT
// ─────────────────────────────────────────────
boot().catch(err => {
  console.error("HomeBridge boot error:", err);
  window.location.href = "login.html";
});

console.log("HomeBridge app.js — clean rebuild. Backend:", BACKEND_URL);

// ─────────────────────────────────────────────
// SECTION 36B: JORDAN PROFILE CARD + REASSIGN
// ─────────────────────────────────────────────
function renderJordanProfileCard() {
  document.getElementById("jordan-profile-card")?.remove();
  const profilePanel = el("profile-panel");
  if (!profilePanel) return;
  const name  = jordanName();
  const brief = jordanBrief();
  const card  = document.createElement("div");
  card.id = "jordan-profile-card";
  card.style.cssText = "max-width:640px;margin:2rem auto 0;padding:1.5rem;background:var(--bg-sunken,#f8f8f6);border:1px solid var(--border);border-radius:12px;";
  card.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:8px;">
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:44px;height:44px;border-radius:50%;background:linear-gradient(135deg,#1749c9,#60a5fa);display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;color:#fff;flex-shrink:0;">${_escHtml(name).charAt(0).toUpperCase()}</div>
        <div>
          <div style="font-size:15px;font-weight:600;color:var(--ink);">${_escHtml(name)}</div>
          <div style="font-size:12px;color:var(--ink-3);">Your Chief of Staff · Always available</div>
        </div>
      </div>
      <span style="font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#1749c9;background:rgba(23,73,201,0.07);border:1px solid rgba(23,73,201,0.18);border-radius:100px;padding:4px 12px;">Chief of Staff</span>
    </div>
    ${brief ? `<div style="font-size:13px;color:var(--ink-2);font-style:italic;margin-bottom:1rem;padding:0.75rem 1rem;background:var(--white,#fff);border-radius:8px;border:1px solid var(--border);">"${_escHtml(brief)}"</div>` : ''}
    <div style="font-size:13px;color:var(--ink-3);line-height:1.65;margin-bottom:1.25rem;">${_escHtml(name)} is always at your side inside the platform — context-aware guidance, quiet nudges, and team introductions when you need them. ${_escHtml(name)} stays out of your way when you don't.</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:.85rem;">
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;letter-spacing:.3px;">Name your Chief of Staff</label>
        <input type="text" id="jordan-rename-input" value="${_escHtml(name)}" placeholder="Jordan" style="width:100%;padding:9px 12px;border:1px solid var(--border);border-radius:6px;font-size:14px;outline:none;" />
      </div>
      <div>
        <label style="display:block;font-size:12px;font-weight:600;color:var(--ink-3);margin-bottom:6px;letter-spacing:.3px;">Character brief <span style="font-weight:400;font-style:italic;">(optional)</span></label>
        <input type="text" id="jordan-rebriefing-input" value="${_escHtml(brief)}" placeholder="e.g. Calm, direct, always has a plan" style="width:100%;padding:9px 12px;border:1px solid var(--border);border-radius:6px;font-size:14px;outline:none;" />
      </div>
    </div>
    <div style="display:flex;gap:.75rem;flex-wrap:wrap;">
      <button onclick="jordanSaveFromProfile()" style="padding:9px 20px;background:#1749c9;color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:500;cursor:pointer;letter-spacing:.2px;">Save Changes</button>
      <button onclick="jordanReassign()" style="padding:9px 16px;background:none;border:1px solid var(--border);border-radius:6px;font-size:13px;color:var(--ink-3);cursor:pointer;">Reassign (start fresh)</button>
    </div>
    <div id="jordan-profile-saved" style="display:none;font-size:13px;color:var(--green);margin-top:.75rem;">✓ Updated — your Chief of Staff is ready.</div>`;
  profilePanel.appendChild(card);
}

function jordanSaveFromProfile() {
  const name  = (document.getElementById("jordan-rename-input")?.value || "").trim() || "Jordan";
  const brief = (document.getElementById("jordan-rebriefing-input")?.value || "").trim();
  jordanSave({ name, brief });
  const fabLabel = document.getElementById("jordan-fab-label");
  if (fabLabel) fabLabel.textContent = `Ask ${name}`;
  const fab = document.getElementById("jordan-fab");
  if (fab) fab.title = `Ask ${name}`;
  const savedMsg = document.getElementById("jordan-profile-saved");
  if (savedMsg) { savedMsg.style.display = "block"; setTimeout(() => { savedMsg.style.display = "none"; renderJordanProfileCard(); }, 1800); }
}

function jordanReassign() {
  if (!confirm("This will reset your Chief of Staff to defaults. You can rename them again right here. Continue?")) return;
  jordanSave({ name: "Jordan", brief: "", namingDone: false, welcomeDone: false });
  renderJordanProfileCard();
  showToast("Chief of Staff reset. Rename them anytime in your Profile.");
}

// ─────────────────────────────────────────────
// SECTION 36C: FLYER EXPORT — Session 28
// ─────────────────────────────────────────────

function openFlyerPreview() {
  const item   = _bcItem;
  if (!item) return;
  const con    = item.content  || {};
  const saved  = getSaved();
  const user   = JSON.parse(localStorage.getItem("hb_user") || "null");
  const isDemo = localStorage.getItem("hb_demo_mode") === "true";

  // Pre-fill content fields
  const headlineEl = document.getElementById("fm-headline");
  const bodyEl     = document.getElementById("fm-body");
  const ctaLabelEl = document.getElementById("fm-cta-label");
  const ctaUrlEl   = document.getElementById("fm-cta-url");
  if (headlineEl) headlineEl.value = con.headline || "";
  if (bodyEl)     bodyEl.value     = con.post     || "";
  if (ctaLabelEl) ctaLabelEl.value = saved.ctaLabel || con.cta || "";
  if (ctaUrlEl)   ctaUrlEl.value   = saved.ctaUrl  || "";

  // Pre-fill agent info from profile
  const agentName  = isDemo ? "Brooke Callahan" : (saved.agentName || user?.agent_name || "");
  const brokerage  = isDemo ? "eXp Realty" : (saved.brokerage || user?.brokerage || "");
  const phone      = isDemo ? "" : (user?.phone || "");
  const email      = isDemo ? "" : (user?.email || "");
  const license    = saved.licenseNumber || "";
  const desigs     = Array.isArray(saved.designations) ? saved.designations.join(", ") : (saved.designations || "");
  const disclaimer = localStorage.getItem("hb_disclaimer") || saved.disclaimer || "";

  const nameEl    = document.getElementById("fm-agent-name");
  const brokEl    = document.getElementById("fm-brokerage");
  const phoneEl   = document.getElementById("fm-phone");
  const emailEl   = document.getElementById("fm-email");
  const licEl     = document.getElementById("fm-license");
  const desigEl   = document.getElementById("fm-designations");
  const discEl    = document.getElementById("fm-disclaimer");
  if (nameEl)    nameEl.value    = agentName;
  if (brokEl)    brokEl.value    = brokerage;
  if (phoneEl)   phoneEl.value   = phone;
  if (emailEl)   emailEl.value   = email;
  if (licEl)     licEl.value     = license;
  if (desigEl)   desigEl.value   = desigs;
  if (discEl)    discEl.value    = disclaimer;

  // Photo opt-in — check if photo exists
  // Profile photo is stored under hb_profile_photo (not in hb_setup)
  const photoCheck = document.getElementById("fm-include-photo");
  const photoHint  = document.getElementById("fm-photo-hint");
  const photoNone  = document.getElementById("fm-photo-none");
  const hasPhoto   = !!(localStorage.getItem("hb_profile_photo"));
  if (photoCheck) { photoCheck.checked = false; photoCheck.disabled = !hasPhoto; }
  if (photoHint)  photoHint.style.display  = hasPhoto ? "block" : "none";
  if (photoNone)  photoNone.style.display  = hasPhoto ? "none"  : "block";

  // Brokerage logo opt-in
  const logoCheck = document.getElementById("fm-include-logo");
  const logoHint  = document.getElementById("fm-logo-hint");
  const logoNone  = document.getElementById("fm-logo-none");
  const hasLogo   = !!(localStorage.getItem("hb_brokerage_logo"));
  if (logoCheck) { logoCheck.checked = false; logoCheck.disabled = !hasLogo; }
  if (logoHint)  logoHint.style.display  = hasLogo ? "block" : "none";
  if (logoNone)  logoNone.style.display  = hasLogo ? "none"  : "block";

  // Open modal
  const backdrop = document.getElementById("flyer-modal-backdrop");
  if (backdrop) backdrop.classList.add("open");
}

function closeFlyerModal() {
  const backdrop = document.getElementById("flyer-modal-backdrop");
  if (backdrop) backdrop.classList.remove("open");
}

function flyerTogglePhoto(checkbox) {
  // Visual feedback only — actual inclusion handled at download time
}

async function downloadFlyer() {
  const btn = document.getElementById("fm-download-btn");
  if (!btn) return;
  const item   = _bcItem;
  if (!item) { showToast("No content selected."); return; }
  const saved  = getSaved();

  const headline     = document.getElementById("fm-headline")?.value.trim()    || "";
  const body         = document.getElementById("fm-body")?.value.trim()        || "";
  const ctaLabel     = document.getElementById("fm-cta-label")?.value.trim()   || "";
  const ctaUrl       = document.getElementById("fm-cta-url")?.value.trim()     || "";
  const agentName    = document.getElementById("fm-agent-name")?.value.trim()  || "";
  const brokerage    = document.getElementById("fm-brokerage")?.value.trim()   || "";
  const phone        = document.getElementById("fm-phone")?.value.trim()       || "";
  const email        = document.getElementById("fm-email")?.value.trim()       || "";
  const licenseNumber= document.getElementById("fm-license")?.value.trim()     || "";
  const designations = document.getElementById("fm-designations")?.value.trim()|| "";
  const disclaimer   = document.getElementById("fm-disclaimer")?.value.trim()  || "";
  const includePhoto = document.getElementById("fm-include-photo")?.checked    || false;
  const includeLogo  = document.getElementById("fm-include-logo")?.checked     || false;
  const photoB64     = (includePhoto) ? (localStorage.getItem("hb_profile_photo") || "") : "";
  const logoB64      = (includeLogo)  ? (localStorage.getItem("hb_brokerage_logo") || "") : "";

  if (!headline && !body) { showToast("Please add a headline or body text before downloading."); return; }

  btn.disabled = true;
  btn.innerHTML = '<span>⏳</span> Generating PDF…';

  try {
    const isDemo = localStorage.getItem("hb_demo_mode") === "true";
    if (isDemo) {
      // Demo mode — simulate delay then show toast
      await new Promise(r => setTimeout(r, 1200));
      showToast("Flyer PDF ready — sign up to download.");
      closeFlyerModal();
      return;
    }

    const payload = {
      item_id:        item.id,
      headline,
      body,
      cta_label:      ctaLabel,
      cta_url:        ctaUrl,
      agent_name:     agentName,
      brokerage,
      phone,
      email,
      license_number: licenseNumber,
      designations,
      disclaimer,
      include_photo:  includePhoto,
      photo_b64:      photoB64,
      include_logo:   includeLogo,
      logo_b64:       logoB64,
    };

    const res = await authFetch(`${BACKEND_URL}/content/flyer`, {
      method: "POST",
      body:   JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    // Trigger browser download
    const blob     = await res.blob();
    const url      = URL.createObjectURL(blob);
    const a        = document.createElement("a");
    a.href         = url;
    a.download     = `AutoMates_Flyer_${(agentName || "Agent").replace(/\s+/g, "_")}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast("Flyer downloaded ✓");
    closeFlyerModal();

  } catch(err) {
    showToast("Could not generate flyer. Please try again.");
    console.error("Flyer error:", err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>🖨</span> Download PDF';
  }
}

// ─────────────────────────────────────────────
// BROKERAGE LOGO UPLOAD — Session 27 (late)
// Stored under hb_brokerage_logo in localStorage.
// Follows same pattern as profile photo upload.
// ─────────────────────────────────────────────

function triggerBrokerageLogoUpload() {
  const input = document.createElement("input");
  input.type  = "file";
  input.accept = "image/*";
  input.onchange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      alert("That logo file is too large. Please use an image under 5MB.");
      return;
    }
    try {
      const base64Jpeg = await _convertBrokerageLogoToJpeg(file);
      localStorage.setItem("hb_brokerage_logo", base64Jpeg);
      _renderBrokerageLogoPreview(base64Jpeg);
      showToast("Brokerage logo saved ✓");
    } catch(err) {
      alert("Could not process that image. Try a PNG or JPEG.");
    }
  };
  input.click();
}

function _convertBrokerageLogoToJpeg(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        // Max 600px wide — preserve aspect ratio for landscape logos
        const MAX_W = 600;
        let w = img.width, h = img.height;
        if (w > MAX_W) { h = Math.round(h * MAX_W / w); w = MAX_W; }
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        canvas.getContext("2d").drawImage(img, 0, 0, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.9));
      };
      img.onerror = () => reject(new Error("Image decode failed"));
      img.src = e.target.result;
    };
    reader.onerror = () => reject(new Error("File read failed"));
    reader.readAsDataURL(file);
  });
}

function _renderBrokerageLogoPreview(base64Jpeg) {
  const preview  = document.getElementById("brokerage-logo-preview");
  const removeBtn = document.getElementById("brokerage-logo-remove-btn");
  if (!preview) return;
  if (base64Jpeg) {
    preview.innerHTML = `<img src="${base64Jpeg}" style="max-width:100%;max-height:100%;object-fit:contain;" alt="Brokerage logo" />`;
    if (removeBtn) removeBtn.style.display = "inline-block";
  } else {
    preview.innerHTML = `<span style="font-size:11px;color:var(--ink-4);">No logo</span>`;
    if (removeBtn) removeBtn.style.display = "none";
  }
}

function removeBrokerageLogo() {
  localStorage.removeItem("hb_brokerage_logo");
  _renderBrokerageLogoPreview(null);
  showToast("Brokerage logo removed.");
}

// Load brokerage logo preview when profile panel renders
// Called from renderProfilePanel() — added to wireProfileAutosave chain
function loadBrokerageLogoPreview() {
  const logo = localStorage.getItem("hb_brokerage_logo");
  _renderBrokerageLogoPreview(logo || null);
}

function flyerToggleLogo(checkbox) {
  // Visual feedback only — actual inclusion handled at download time
}
