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
