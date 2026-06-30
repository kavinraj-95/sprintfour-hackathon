// Presentation helpers + the linked-resolution rule, kept out of components so
// the visual layer stays declarative and the rules are tested in one place.

import type { PiiType, ReviewItem, ReviewTier } from "../types/contract";

// ---- tiers --------------------------------------------------------------
// One vocabulary shared with the merge step. Tier 1 is the dangerous miss.

interface TierMeta {
  tier: ReviewTier;
  label: string;
  blurb: string; // why this tier needs attention, in Sam's terms
  accent: string; // tailwind border/text accent
  chip: string; // tailwind chip bg+text
}

export const TIERS: Record<ReviewTier, TierMeta> = {
  1: {
    tier: 1,
    label: "High risk",
    blurb: "Structured PII or a duplicate left visible. A miss here is the leak.",
    accent: "border-l-red-500",
    chip: "bg-red-100 text-red-800",
  },
  2: {
    tier: 2,
    label: "Low confidence",
    blurb: "Flagged but uncertain — likely a needless hide. Confirm or flip.",
    accent: "border-l-amber-400",
    chip: "bg-amber-100 text-amber-800",
  },
  3: {
    tier: 3,
    label: "Soft review",
    blurb: "Model-only hunch with no structural backup. Dismiss freely.",
    accent: "border-l-sky-400",
    chip: "bg-sky-100 text-sky-800",
  },
};

export const TIER_ORDER: ReviewTier[] = [1, 2, 3];

// ---- pii type styling ---------------------------------------------------

export const TYPE_LABEL: Record<PiiType, string> = {
  PERSON: "Person",
  ORG: "Organisation",
  EMAIL: "Email",
  PHONE: "Phone",
  ADDRESS: "Address",
  ID_NUMBER: "ID number",
  OTHER: "Other",
};

export function typeChipClass(_type: PiiType): string {
  // Type is informational, not a risk signal — keep it neutral so the tier
  // colour carries the urgency and types never compete with it.
  return "bg-slate-100 text-slate-700";
}

// ---- confidence cue -----------------------------------------------------

// Opacity is the confidence channel in the document view; here we surface a
// short word + a value so the queue is scannable without a meter widget.
export function confidenceWord(c: number): string {
  if (c >= 0.95) return "near-certain";
  if (c >= 0.8) return "likely";
  if (c >= 0.6) return "possible";
  return "weak";
}

// Map a 0..1 confidence to an opacity floor of 0.35 so even weak findings stay
// legible — an invisible miss must never be made MORE invisible by low opacity.
export function confidenceOpacity(c: number): number {
  return 0.35 + 0.65 * Math.min(1, Math.max(0, c));
}

// ---- codepoint-safe slicing (the offset rule) ---------------------------
// Offsets are codepoint indices into original_text; index via Array.from so
// astral characters (emoji/CJK) never shift the highlight off the real span.

export function codepoints(text: string): string[] {
  return Array.from(text);
}

export function sliceCp(cps: string[], start: number, end: number): string {
  return cps.slice(start, end).join("");
}

// ---- linked-duplicate resolution ----------------------------------------
// "Fix all N places at once" is enforced SERVER-SIDE: one accept/dismiss on a
// linked item cascades to every linked occurrence and is logged as a single
// undoable step. The UI sends one action and shows the count below.

// "fixes N places" — the human count including this occurrence.
export function placesCount(item: ReviewItem): number {
  return item.linked_count + 1;
}

// ---- status helpers -----------------------------------------------------

export function isResolved(item: ReviewItem): boolean {
  return item.status !== "pending";
}
