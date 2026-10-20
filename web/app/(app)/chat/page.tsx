import { redirect } from "next/navigation";

/** Chat lives at `/`; keep `/chat` as an alias. */
export default function ChatPage() {
  redirect("/");
}
