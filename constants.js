/**
 * Application Constants
 *
 * Centralized configuration for business rules,
 * seat limits, and application settings.
 */

export const SEAT_LIMITS = {
  COLORADO: parseInt(process.env.COLORADO_SEAT_LIMIT) || 100,
  ENABLED: process.env.SEAT_LIMIT_ENABLED === "true",
};

export const USER_ROLES = {
  FAMILY_MEMBER: "family_member",
  RESPONSIBLE_ONE: "responsible_one",
  CAREGIVER: "caregiver",
  ADMIN: "admin",
};

export const FAMILY_SITUATIONS = {
  INHERITED_HOME: "inherited_home",
  AGING_PARENT: "aging_parent",
  SELLING_FAMILY_HOME: "selling_family_home",
  DOWNSIZING: "downsizing",
  MULTIPLE_PROPERTIES: "multiple_properties",
  ESTATE_SETTLEMENT: "estate_settlement",
};

export const EMOTIONAL_SIGNALS = {
  OVERWHELMED: "overwhelmed",
  RESPONSIBLE: "responsible",
  CONFLICTED: "conflicted",
  GRIEVING: "grieving",
  PRACTICAL: "practical",
  UNCERTAIN: "uncertain",
};

export const ONBOARDING_STAGES = {
  INITIAL_SITUATION: "initial_situation",
  EMOTIONAL_CHECK: "emotional_check",
  ROLE_IDENTIFICATION: "role_identification",
  NEEDS_ASSESSMENT: "needs_assessment",
  CLARITY_ROADMAP: "clarity_roadmap",
};

export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  TOO_MANY_REQUESTS: 429,
  INTERNAL_ERROR: 500,
};
