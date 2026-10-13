// Friendly names for the generated API types. Regenerate with `npm run gen:api` after changing the API.
import type { components } from "./api-schema";

type Schemas = components["schemas"];

export type Person = Schemas["Person"];
export type Role = Schemas["Role"];
export type Flag = Schemas["FlagOut"];
export type FlagUpdate = Schemas["FlagUpdate"];
export type FlagStatus = Schemas["FlagStatus"];
export type FlagRole = Schemas["FlagRole"];
export type RuleKey = Schemas["RuleKey"];
export type PersonProfile = Schemas["PersonProfile"];
export type RoleSummary = Schemas["RoleSummary"];
export type Pattern = Schemas["PatternOut"];
export type PendingReview = Schemas["PendingReview"];
export type ReviewActivity = Schemas["ReviewActivity"];
export type LoadReport = Schemas["LoadReport"];
export type LoadRow = Schemas["LoadRow"];
export type QualityReport = Schemas["QualityReport"];
export type QualityRow = Schemas["QualityRow"];
export type Overview = Schemas["Overview"];
export type HealthPart = Schemas["HealthPart"];
export type HealthPartKey = Schemas["HealthPartKey"];
export type RuleSettings = Schemas["RuleSettings"];
export type SettingsOut = Schemas["SettingsOut"];
export type SettingsSaved = Schemas["SettingsSaved"];
export type EngineRun = Schemas["EngineRun"];
export type DemoReset = Schemas["DemoReset"];
