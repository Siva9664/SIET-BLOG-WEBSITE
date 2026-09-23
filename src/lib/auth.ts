import { cookies } from "next/headers";
import type { User } from "./types";

export async function getSession(): Promise<User | null> {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;
    const cookieHeader = cookieStore.toString();

    if (!token && (!cookieHeader || !cookieHeader.includes("access_token="))) {
      return null;
    }

    const effectiveToken = token || (cookieHeader.split("access_token=")[1]?.split(";")[0]?.trim());

    const BASE = `${process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"}/api/v1`;
    const res = await fetch(`${BASE}/auth/me`, {
      headers: {
        "Content-Type": "application/json",
        ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {}),
        Cookie: cookieHeader || (effectiveToken ? `access_token=${effectiveToken}` : ""),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      return null;
    }

    const user = await res.json();
    return user as User;
  } catch (error) {
    console.warn("getSession: Authentication fetch failed or was offline.", error);
    return null;
  }
}
