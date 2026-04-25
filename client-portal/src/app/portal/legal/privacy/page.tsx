import { redirect } from "next/navigation";

// Legal pages moved to the public /legal namespace so they're readable
// without auth. Preserve any inbound links by 308-redirecting.
export default function LegacyPrivacyRedirect() {
  redirect("/legal/privacy");
}
