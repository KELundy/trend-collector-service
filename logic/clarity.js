// Denver-specific onboarding flow

export function getDenverOnboardingQuestions() {
  return [
    {
      id: "who_are_you",
      label: "Which one sounds most like you?",
      type: "single-choice",
      options: [
        "Adult daughter in Denver trying to manage this",
        "Spouse or partner who’s overwhelmed",
        "Adult child who lives out of state",
        "Other"
      ]
    },
    {
      id: "where_is_person",
      label: "Where is your family member right now?",
      type: "single-choice",
      options: [
        "At home in the Denver area",
        "In a Denver hospital",
        "In rehab or a skilled nursing facility",
        "In assisted living or memory care",
        "Out of state"
      ]
    },
    {
      id: "home_setup",
      label: "What best describes their current home setup?",
      type: "single-choice",
      options: [
        "Split-level or two-story with stairs",
        "Single-level home or condo",
        "Apartment or senior community",
        "I’m not sure / it’s complicated"
      ]
    },
    {
      id: "biggest_concern",
      label: "What is weighing on you the most right now?",
      type: "single-choice",
      options: [
        "Safety and falls",
        "Memory or confusion",
        "Getting in and out of the house (snow/ice, stairs, mobility)",
        "Keeping up with the house",
        "Family not on the same page",
        "Money and what care will cost"
      ]
    },
    {
      id: "timeline",
      label: "How urgent does this feel?",
      type: "single-choice",
      options: [
        "We have to make decisions in the next day or two",
        "We have a little time, but it’s starting to feel pressing",
        "We’re trying to think ahead before it becomes a crisis"
      ]
    },
    {
      id: "move_or_stay",
      label: "Are you mostly trying to:",
      type: "single-choice",
      options: [
        "Keep them safely in their current home",
        "Figure out if a different home or setting would be better",
        "I honestly don’t know yet"
      ]
    },
    {
      id: "anything_else",
      label: "In a sentence or two, what would you say if you could only explain this once?",
      type: "text"
    }
  ];
}

export function analyzeDenverOnboardingResponses(responses) {
  // responses is expected to be an object keyed by question id
  const parts = [];

  if (responses.who_are_you) {
    parts.push(`You’re coming to this as ${responses.who_are_you.toLowerCase()}.`);
  }

  if (responses.where_is_person) {
    parts.push(`Right now, your family member is ${responses.where_is_person.toLowerCase()}.`);
  }

  if (responses.home_setup) {
    parts.push(`Their current home setup is: ${responses.home_setup.toLowerCase()}.`);
  }

  if (responses.biggest_concern) {
    parts.push(`What’s weighing on you most is ${responses.biggest_concern.toLowerCase()}.`);
  }

  if (responses.timeline) {
    parts.push(`In terms of timing, it feels like: ${responses.timeline.toLowerCase()}.`);
  }

  if (responses.move_or_stay) {
    parts.push(`You’re mostly trying to ${responses.move_or_stay.toLowerCase()}.`);
  }

  if (responses.anything_else) {
    parts.push(`In your own words: ${responses.anything_else}`);
  }

  const narrativeInput = parts.join(" ");

  const situation = analyzeSituation(narrativeInput);

  return {
    onboardingSummary: {
      narrative: narrativeInput,
      promise: "You don’t have to figure this out alone. This just gives us a clearer picture so we can talk about real options, not guesses."
    },
    situation
  };
}

// Core clarity engine

export function analyzeSituation(input) {
  const issue = identifyIssue(input);
  const constraints = identifyConstraints(input);
  const choices = generateChoices(input);
  const { confidence, confidenceExplanation } = determineConfidence(
    issue,
    constraints,
    choices
  );

  return {
    rawInput: input,
    issue,
    constraints,
    choices,
    confidence,
    confidenceExplanation,
    summary: generateSummary(issue, constraints, choices),
  };
}

// Multi-issue prioritized issue detector
function identifyIssue(input) {
  const text = input.toLowerCase();

  // PRIORITY 1 — Immediate safety & legal barriers

  // Safety / hospital
  if (text.includes("hospital") && text.includes("can't go home")) {
    return "A care decision needs to be made right away because going back home is not an option as things stand.";
  }

  // Falls
  if (text.includes("fell") || text.includes("fall")) {
    return "A safety event, like a fall, has forced everyone to pay attention and make decisions sooner than expected.";
  }

  // Legal / authority
  if (
    text.includes("poa") ||
    text.includes("power of attorney") ||
    text.includes("no power of attorney") ||
    text.includes("no poa") ||
    text.includes("guardianship") ||
    text.includes("conservator") ||
    text.includes("no one can decide") ||
    text.includes("no one has authority") ||
    text.includes("hospital needs paperwork") ||
    text.includes("they won't let me sign") ||
    text.includes("cant sign") ||
    text.includes("can't sign") ||
    text.includes("capacity") ||
    text.includes("not capable of deciding") ||
    text.includes("doctor says they lack capacity")
  ) {
    return "There is a real question about who is allowed to make decisions or sign paperwork on your family member’s behalf.";
  }

  // PRIORITY 2 — Functional decline & home mismatch

  // Medical complexity / cognitive shift
  if (
    text.includes("confused") ||
    text.includes("confusion") ||
    text.includes("memory") ||
    text.includes("forget") ||
    text.includes("not herself") ||
    text.includes("not himself") ||
    text.includes("declining") ||
    text.includes("getting worse") ||
    text.includes("worse") ||
    text.includes("weaker") ||
    text.includes("not bouncing back") ||
    text.includes("parkinson") ||
    text.includes("stroke") ||
    text.includes("dementia") ||
    text.includes("alzheimer") ||
    text.includes("wandering") ||
    text.includes("medication") ||
    text.includes("delirium")
  ) {
    return "A medical change or shift in thinking is affecting safety, independence, and how decisions can be made.";
  }

  // Home / environment mismatch
  if (
    text.includes("too many stairs") ||
    text.includes("stairs are a problem") ||
    text.includes("can't do the stairs") ||
    text.includes("cant do the stairs") ||
    text.includes("can't manage the stairs") ||
    text.includes("cant manage the stairs") ||
    text.includes("house is too big") ||
    text.includes("home is too big") ||
    text.includes("can't keep up with the house") ||
    text.includes("cant keep up with the house") ||
    text.includes("can't keep up with the home") ||
    text.includes("cant keep up with the home") ||
    text.includes("unsafe at home") ||
    text.includes("not safe at home") ||
    text.includes("can't be left alone") ||
    text.includes("cant be left alone") ||
    text.includes("can't live alone") ||
    text.includes("cant live alone") ||
    text.includes("wandering outside") ||
    text.includes("leaves the house") ||
    text.includes("gets lost") ||
    text.includes("forgets the stove") ||
    text.includes("left the stove on") ||
    text.includes("kitchen isn't safe") ||
    text.includes("kitchen isnt safe") ||
    text.includes("bathroom isn't safe") ||
    text.includes("bathroom isnt safe") ||
    text.includes("can't get to the bathroom") ||
    text.includes("cant get to the bathroom") ||
    text.includes("can't get in the shower") ||
    text.includes("cant get in the shower") ||
    text.includes("house doesn't work anymore") ||
    text.includes("house doesnt work anymore") ||
    text.includes("home doesn't work anymore") ||
    text.includes("home doesnt work anymore")
  ) {
    return "The current home setup no longer matches what your family member can safely manage day to day.";
  }

  // PRIORITY 3 — Emotional & relational load

  // Responsible One severity (near limit)
  if (
    text.includes("i can't keep doing this") ||
    text.includes("i cant keep doing this") ||
    text.includes("i'm drowning") ||
    text.includes("im drowning") ||
    text.includes("i'm falling apart") ||
    text.includes("im falling apart") ||
    text.includes("i can't handle this") ||
    text.includes("i cant handle this") ||
    text.includes("i'm at my limit") ||
    text.includes("im at my limit")
  ) {
    return "The person trying to hold everything together is at or near their limit and cannot keep going like this.";
  }

  // Caregiver burnout
  if (
    text.includes("i'm exhausted") ||
    text.includes("im exhausted") ||
    text.includes("i'm so tired") ||
    text.includes("im so tired") ||
    text.includes("i'm worn out") ||
    text.includes("im worn out") ||
    text.includes("i'm burned out") ||
    text.includes("im burned out") ||
    text.includes("i'm burnt out") ||
    text.includes("im burnt out") ||
    text.includes("i can't keep up") ||
    text.includes("i cant keep up") ||
    text.includes("i'm overwhelmed by caregiving") ||
    text.includes("im overwhelmed by caregiving") ||
    text.includes("i'm doing everything for them") ||
    text.includes("im doing everything for them") ||
    text.includes("i'm taking care of them full time") ||
    text.includes("im taking care of them full time")
  ) {
    return "The current caregiving load is too heavy for one person and is no longer sustainable.";
  }

  // Responsible One (identity)
  if (
    text.includes("i'm the only one") ||
    text.includes("i am the only one") ||
    text.includes("i'm doing this alone") ||
    text.includes("i am doing this alone") ||
    text.includes("no one else will help") ||
    text.includes("i have to figure this out") ||
    text.includes("it's on me") ||
    text.includes("its on me") ||
    text.includes("falls on me") ||
    text.includes("i guess it's up to me") ||
    text.includes("i guess its up to me") ||
    text.includes("i'm trying to manage this") ||
    text.includes("im trying to manage this") ||
    text.includes("i'm trying to handle this") ||
    text.includes("im trying to handle this")
  ) {
    return "The person reaching out is carrying the responsibility for this situation largely on their own.";
  }

  // Family dynamics
  if (
    text.includes("my brother") ||
    text.includes("my sister") ||
    text.includes("siblings") ||
    text.includes("family disagrees") ||
    text.includes("no one agrees") ||
    text.includes("out of state") ||
    text.includes("won't help") ||
    text.includes("wont help") ||
    text.includes("refuses") ||
    text.includes("arguing") ||
    text.includes("fight") ||
    text.includes("conflict")
  ) {
    return "Family dynamics and disagreements are making it harder to move forward together.";
  }

  // Financial pressure
  if (
    text.includes("can't afford") ||
    text.includes("cant afford") ||
    text.includes("cannot afford") ||
    text.includes("too expensive") ||
    text.includes("no money") ||
    text.includes("medicare won't cover") ||
    text.includes("medicare wont cover") ||
    text.includes("medicaid won't cover") ||
    text.includes("medicaid wont cover") ||
    text.includes("no insurance") ||
    text.includes("no long-term care") ||
    text.includes("no long term care") ||
    text.includes("ltc") ||
    text.includes("cost")
  ) {
    return "Money, coverage, and the cost of care are shaping what feels possible right now.";
  }

  return "The primary issue is not fully clear yet and needs a bit more information.";
}

function identifyConstraints(input) {
  const text = input.toLowerCase();
  const constraints = [];

  // Safety / home
  if (text.includes("can't go home") || text.includes("cannot go home") || text.includes("cant go home")) {
    constraints.push("Going back to the current home does not feel safe or realistic right now.");
  }

  // Falls
  if (text.includes("fell") || text.includes("fall")) {
    constraints.push("There is a higher risk of falls or injury that cannot be ignored.");
  }

  // Hospital
  if (text.includes("hospital")) {
    constraints.push("There is pressure from the hospital or facility to make a discharge plan.");
  }

  // Medical complexity
  if (
    text.includes("confused") ||
    text.includes("confusion") ||
    text.includes("memory") ||
    text.includes("forget") ||
    text.includes("not herself") ||
    text.includes("not himself") ||
    text.includes("declining") ||
    text.includes("getting worse") ||
    text.includes("worse") ||
    text.includes("weaker") ||
    text.includes("not bouncing back") ||
    text.includes("parkinson") ||
    text.includes("stroke") ||
    text.includes("dementia") ||
    text.includes("alzheimer") ||
    text.includes("wandering") ||
    text.includes("medication") ||
    text.includes("delirium")
  ) {
    constraints.push(
      "Changes in health or thinking are limiting independence and increasing the need for support or supervision."
    );
  }

  // Home / environment mismatch
  if (
    text.includes("too many stairs") ||
    text.includes("stairs are a problem") ||
    text.includes("can't do the stairs") ||
    text.includes("cant do the stairs") ||
    text.includes("can't manage the stairs") ||
    text.includes("cant manage the stairs") ||
    text.includes("house is too big") ||
    text.includes("home is too big") ||
    text.includes("can't keep up with the house") ||
    text.includes("cant keep up with the house") ||
    text.includes("can't keep up with the home") ||
    text.includes("cant keep up with the home") ||
    text.includes("unsafe at home") ||
    text.includes("not safe at home") ||
    text.includes("can't be left alone") ||
    text.includes("cant be left alone") ||
    text.includes("can't live alone") ||
    text.includes("cant live alone") ||
    text.includes("wandering outside") ||
    text.includes("leaves the house") ||
    text.includes("gets lost") ||
    text.includes("forgets the stove") ||
    text.includes("left the stove on") ||
    text.includes("kitchen isn't safe") ||
    text.includes("kitchen isnt safe") ||
    text.includes("bathroom isn't safe") ||
    text.includes("bathroom isnt safe") ||
    text.includes("can't get to the bathroom") ||
    text.includes("cant get to the bathroom") ||
    text.includes("can't get in the shower") ||
    text.includes("cant get in the shower") ||
    text.includes("house doesn't work anymore") ||
    text.includes("house doesnt work anymore") ||
    text.includes("home doesn't work anymore") ||
    text.includes("home doesnt work anymore")
  ) {
    constraints.push(
      "The way the home is set up, or the level of supervision available, does not match current abilities and safety needs."
    );
  }

  // Legal / authority
  if (
    text.includes("poa") ||
    text.includes("power of attorney") ||
    text.includes("no power of attorney") ||
    text.includes("no poa") ||
    text.includes("guardianship") ||
    text.includes("conservator") ||
    text.includes("no one can decide") ||
    text.includes("no one has authority") ||
    text.includes("hospital needs paperwork") ||
    text.includes("they won't let me sign") ||
    text.includes("cant sign") ||
    text.includes("can't sign") ||
    text.includes("capacity") ||
    text.includes("not capable of deciding") ||
    text.includes("doctor says they lack capacity")
  ) {
    constraints.push(
      "There is uncertainty or disagreement about who has the legal authority to act or sign on your family member’s behalf."
    );
  }

  // Responsible One (identity)
  if (
    text.includes("i'm the only one") ||
    text.includes("i am the only one") ||
    text.includes("i'm doing this alone") ||
    text.includes("i am doing this alone") ||
    text.includes("no one else will help") ||
    text.includes("i have to figure this out") ||
    text.includes("it's on me") ||
    text.includes("its on me") ||
    text.includes("falls on me") ||
    text.includes("i guess it's up to me") ||
    text.includes("i guess its up to me") ||
    text.includes("i'm trying to manage this") ||
    text.includes("im trying to manage this") ||
    text.includes("i'm trying to handle this") ||
    text.includes("im trying to handle this")
  ) {
    constraints.push(
      "Most of the responsibility for this situation is falling on one person instead of being shared."
    );
  }

  // Responsible One severity
  if (
    text.includes("i can't keep doing this") ||
    text.includes("i cant keep doing this") ||
    text.includes("i'm drowning") ||
    text.includes("im drowning") ||
    text.includes("i'm falling apart") ||
    text.includes("im falling apart") ||
    text.includes("i can't handle this") ||
    text.includes("i cant handle this") ||
    text.includes("i'm at my limit") ||
    text.includes("im at my limit")
  ) {
    constraints.push(
      "The person trying to manage everything is overwhelmed and needs immediate clarity and relief, not more tasks."
    );
  }

  // Caregiver burnout
  if (
    text.includes("i'm exhausted") ||
    text.includes("im exhausted") ||
    text.includes("i'm so tired") ||
    text.includes("im so tired") ||
    text.includes("i'm worn out") ||
    text.includes("im worn out") ||
    text.includes("i'm burned out") ||
    text.includes("im burned out") ||
    text.includes("i'm burnt out") ||
    text.includes("im burnt out") ||
    text.includes("i can't keep up") ||
    text.includes("i cant keep up") ||
    text.includes("i'm overwhelmed by caregiving") ||
    text.includes("im overwhelmed by caregiving") ||
    text.includes("i'm doing everything for them") ||
    text.includes("im doing everything for them") ||
    text.includes("i'm taking care of them full time") ||
    text.includes("im taking care of them full time")
  ) {
    constraints.push(
      "The current caregiving load is too heavy for one person to sustain without more support or a different plan."
    );
  }

  // Family conflict
  if (
    text.includes("my brother") ||
    text.includes("my sister") ||
    text.includes("siblings") ||
    text.includes("family disagrees") ||
    text.includes("no one agrees") ||
    text.includes("out of state") ||
    text.includes("won't help") ||
    text.includes("wont help") ||
    text.includes("refuses") ||
    text.includes("arguing") ||
    text.includes("fight") ||
    text.includes("conflict")
  ) {
    constraints.push(
      "Family disagreement, distance, or uneven involvement is making it harder to move forward together."
    );
  }

  // Financial pressure
  if (
    text.includes("can't afford") ||
    text.includes("cant afford") ||
    text.includes("cannot afford") ||
    text.includes("too expensive") ||
    text.includes("no money") ||
    text.includes("medicare won't cover") ||
    text.includes("medicare wont cover") ||
    text.includes("medicaid won't cover") ||
    text.includes("medicaid wont cover") ||
    text.includes("no insurance") ||
    text.includes("no long-term care") ||
    text.includes("no long term care") ||
    text.includes("ltc") ||
    text.includes("cost")
  ) {
    constraints.push(
      "Money, coverage, and the cost of care are real limits that have to be factored into any plan."
    );
  }

  if (constraints.length === 0) {
    constraints.push("There are likely real limits here, but they are not fully clear yet from what’s been shared.");
  }

  return constraints;
}

function generateChoices(input) {
  const text = input.toLowerCase();
  const choices = [];

  // Safety / hospital / home choices
  if (text.includes("hospital") && text.includes("can't go home")) {
    choices.push(
      "Ask the hospital team whether they expect a discharge today, tomorrow, or later this week so the timeline is clear."
    );
    choices.push("Clarify whether short-term rehab is an option being considered.");
    choices.push("Get a sense of what 24/7 care at home would realistically look like, even if it’s just a rough picture.");
    choices.push("Ask whether this was the first fall or part of a pattern over the last few months.");
    choices.push("Check if there have been recent changes in walking, balance, or strength.");
  }

  // Falls choices
  if (text.includes("fell") || text.includes("fall")) {
    choices.push("Clarify when the fall happened and what was going on right before it.");
    choices.push("Ask whether this was a one-time event or one of several falls recently.");
  }

  // Medical complexity choices
  if (
    text.includes("confused") ||
    text.includes("confusion") ||
    text.includes("memory") ||
    text.includes("forget") ||
    text.includes("not herself") ||
    text.includes("not himself") ||
    text.includes("declining") ||
    text.includes("getting worse") ||
    text.includes("worse") ||
    text.includes("weaker") ||
    text.includes("not bouncing back") ||
    text.includes("parkinson") ||
    text.includes("stroke") ||
    text.includes("dementia") ||
    text.includes("alzheimer") ||
    text.includes("wandering") ||
    text.includes("medication") ||
    text.includes("delirium")
  ) {
    choices.push(
      "Clarify whether these changes are new and sudden, or part of a slower pattern over time."
    );
    choices.push(
      "Ask whether a doctor, nurse, or therapist has recently evaluated these changes and what they said."
    );
    choices.push("Get clear on whether your family member needs someone nearby or checking in often for safety.");
    choices.push(
      "Ask if rehab, home health, or a higher level of care has been mentioned as an option."
    );
  }

  // Home / environment mismatch choices
  if (
    text.includes("too many stairs") ||
    text.includes("stairs are a problem") ||
    text.includes("can't do the stairs") ||
    text.includes("cant do the stairs") ||
    text.includes("can't manage the stairs") ||
    text.includes("cant manage the stairs") ||
    text.includes("house is too big") ||
    text.includes("home is too big") ||
    text.includes("can't keep up with the house") ||
    text.includes("cant keep up with the house") ||
    text.includes("can't keep up with the home") ||
    text.includes("cant keep up with the home") ||
    text.includes("unsafe at home") ||
    text.includes("not safe at home") ||
    text.includes("can't be left alone") ||
    text.includes("cant be left alone") ||
    text.includes("can't live alone") ||
    text.includes("cant live alone") ||
    text.includes("wandering outside") ||
    text.includes("leaves the house") ||
    text.includes("gets lost") ||
    text.includes("forgets the stove") ||
    text.includes("left the stove on") ||
    text.includes("kitchen isn't safe") ||
    text.includes("kitchen isnt safe") ||
    text.includes("bathroom isn't safe") ||
    text.includes("bathroom isnt safe") ||
    text.includes("can't get to the bathroom") ||
    text.includes("cant get to the bathroom") ||
    text.includes("can't get in the shower") ||
    text.includes("cant get in the shower") ||
    text.includes("house doesn't work anymore") ||
    text.includes("house doesnt work anymore") ||
    text.includes("home doesn't work anymore") ||
    text.includes("home doesnt work anymore")
  ) {
    choices.push(
      "Name which parts of the home are hardest right now (stairs, bathroom, kitchen, entry, getting in and out)."
    );
    choices.push(
      "Get clear on whether someone needs to be present, nearby, or checking in often for the home to feel safe."
    );
    choices.push(
      "Consider whether simple changes (equipment, layout, support) could make the home workable for a short period, even if it’s not a long-term solution."
    );
    choices.push(
      "Notice whether anyone has already brought up the idea of a different home or setting, even casually."
    );
  }

  // Legal / authority choices
  if (
    text.includes("poa") ||
    text.includes("power of attorney") ||
    text.includes("no power of attorney") ||
    text.includes("no poa") ||
    text.includes("guardianship") ||
    text.includes("conservator") ||
    text.includes("no one can decide") ||
    text.includes("no one has authority") ||
    text.includes("hospital needs paperwork") ||
    text.includes("they won't let me sign") ||
    text.includes("cant sign") ||
    text.includes("can't sign") ||
    text.includes("capacity") ||
    text.includes("not capable of deciding") ||
    text.includes("doctor says they lack capacity")
  ) {
    choices.push(
      "Find out whether any Power of Attorney documents exist and, if so, who is named in them."
    );
    choices.push(
      "Ask whether the medical team believes your family member can still make their own decisions right now."
    );
    choices.push(
      "Clarify what specific paperwork the hospital or facility is asking for."
    );
    choices.push(
      "Note whether an attorney, case manager, or social worker is already involved who can help with the legal side."
    );
  }

  // Financial choices
  if (
    text.includes("can't afford") ||
    text.includes("cant afford") ||
    text.includes("cannot afford") ||
    text.includes("too expensive") ||
    text.includes("no money") ||
    text.includes("medicare won't cover") ||
    text.includes("medicare wont cover") ||
    text.includes("medicaid won't cover") ||
    text.includes("medicaid wont cover") ||
    text.includes("no insurance") ||
    text.includes("no long-term care") ||
    text.includes("no long term care") ||
    text.includes("ltc") ||
    text.includes("cost")
  ) {
    choices.push("Ask what Medicare or Medicaid will and will not cover in this situation.");
    choices.push(
      "Clarify whether short-term rehab is available under Medicare and what the limits are."
    );
    choices.push("Get a rough sense of what home care hours might cost at different levels of support.");
    choices.push(
      "Ask whether the hospital or facility has a financial counselor or case manager who can walk through options."
    );
  }

  // Responsible One choices
  if (
    text.includes("i'm the only one") ||
    text.includes("i am the only one") ||
    text.includes("i'm doing this alone") ||
    text.includes("i am doing this alone") ||
    text.includes("no one else will help") ||
    text.includes("i have to figure this out") ||
    text.includes("it's on me") ||
    text.includes("its on me") ||
    text.includes("falls on me") ||
    text.includes("i guess it's up to me") ||
    text.includes("i guess its up to me") ||
    text.includes("i'm trying to manage this") ||
    text.includes("im trying to manage this") ||
    text.includes("i'm trying to handle this") ||
    text.includes("im trying to handle this")
  ) {
    choices.push("Name the one or two decisions that actually need to be made first.");
    choices.push("List which tasks could be shared, delegated, or delayed, even if it feels hard to ask.");
    choices.push("Separate immediate safety issues from everything else that can wait a bit.");
    choices.push(
      "Notice whether any professionals (doctors, social workers, case managers, real estate or senior specialists) are already in the picture who could share some of the load."
    );
  }

  // Responsible One severity choices
  if (
    text.includes("i can't keep doing this") ||
    text.includes("i cant keep doing this") ||
    text.includes("i'm drowning") ||
    text.includes("im drowning") ||
    text.includes("i'm falling apart") ||
    text.includes("im falling apart") ||
    text.includes("i can't handle this") ||
    text.includes("i cant handle this") ||
    text.includes("i'm at my limit") ||
    text.includes("im at my limit")
  ) {
    choices.push(
      "Identify the single most urgent issue that needs attention right now, even if everything feels urgent."
    );
    choices.push(
      "Set aside anything that is not about immediate safety or time-sensitive decisions until things are more stable."
    );
    choices.push(
      "Notice whether there is even one person or professional who could help carry a small part of this with you."
    );
    choices.push("Break the situation into one or two next steps that feel doable in the next day or two.");
  }

  // Caregiver burnout choices
  if (
    text.includes("i'm exhausted") ||
    text.includes("im exhausted") ||
    text.includes("i'm so tired") ||
    text.includes("im so tired") ||
    text.includes("i'm worn out") ||
    text.includes("im worn out") ||
    text.includes("i'm burned out") ||
    text.includes("im burned out") ||
    text.includes("i'm burnt out") ||
    text.includes("im burnt out") ||
    text.includes("i can't keep up") ||
    text.includes("i cant keep up") ||
    text.includes("i'm overwhelmed by caregiving") ||
    text.includes("im overwhelmed by caregiving") ||
    text.includes("i'm doing everything for them") ||
    text.includes("im doing everything for them") ||
    text.includes("i'm taking care of them full time") ||
    text.includes("im taking care of them full time")
  ) {
    choices.push(
      "Name which caregiving tasks are taking the most energy from you right now."
    );
    choices.push(
      "Consider whether any of those tasks could be shared, outsourced, or reduced, even temporarily."
    );
    choices.push(
      "Ask whether short-term support (home care, respite, family help) is available, even for a few hours."
    );
    choices.push(
      "Separate what has to happen this week from what can be revisited once things are more stable."
    );
  }

  // Family conflict / dynamics choices
  if (
    text.includes("my brother") ||
    text.includes("my sister") ||
    text.includes("siblings") ||
    text.includes("family disagrees") ||
    text.includes("no one agrees") ||
    text.includes("out of state") ||
    text.includes("won't help") ||
    text.includes("wont help") ||
    text.includes("refuses") ||
    text.includes("arguing") ||
    text.includes("fight") ||
    text.includes("conflict")
  ) {
    choices.push("Clarify who actually has decision-making authority right now, legally or practically.");
    choices.push("List who is truly available to help, even in small ways, versus who is not.");
    choices.push("Separate immediate safety and care needs from longer-term disagreements about what should happen.");
    choices.push(
      "Consider whether a neutral third party (case manager, social worker, senior-focused professional) could help keep conversations grounded."
    );
  }

  // Fallback
  if (choices.length === 0) {
    choices.push("Gather a bit more detail about what has changed recently and what feels most urgent.");
    choices.push("Name the one thing that worries you most when you think about the next few weeks.");
  }

  return choices;
}

function determineConfidence(issue, constraints, choices) {
  if (issue.startsWith("The primary issue is not fully clear")) {
    return {
      confidence: "low",
      confidenceExplanation:
        "This situation needs a bit more detail before the next steps become obvious. A clearer picture will make the options easier to see."
    };
  }

  const constraintCount = constraints ? constraints.length : 0;
  const choiceCount = choices ? choices.length : 0;

  if (constraintCount >= 1 && choiceCount >= 2) {
    return {
      confidence: "high",
      confidenceExplanation:
        "This situation is fairly clear. The main issue and what’s getting in the way are both visible, which makes it easier to talk about real options."
    };
  }

  return {
    confidence: "medium",
    confidenceExplanation:
      "This situation is partly clear. We can see some of the picture, but a few more details would help sharpen the next steps."
  };
}

function generateSummary(issue, constraints, choices) {
  return `
Here’s what this situation looks like in plain terms:

${issue}

What seems to be getting in the way:
- ${constraints.join("\n- ")}

Next choices to get oriented and moving:
- ${choices.join("\n- ")}
  `.trim();
}
