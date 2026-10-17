// ngraph.jp にはログインが無い。テレスとの対話（要ログイン）は出さない
export function useSession() {
  return { data: null, status: "unauthenticated" as const };
}
