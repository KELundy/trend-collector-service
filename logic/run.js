import { healthCheck } from "./health.js";
import { detailedHealthCheck } from "./details.js";
import { analyzeSituation } from "./clarity.js";

console.log("Health check result:");
console.log(healthCheck());

console.log("Detailed health check:");
console.log(detailedHealthCheck());

const result = analyzeSituation(
  `We don’t have POA, the hospital needs paperwork, my siblings are out of state.`,
);

console.log("Clarity engine full output:");
console.log(result);

console.log("\nSummary output:");
console.log(result.summary);
