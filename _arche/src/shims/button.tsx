import type { ButtonHTMLAttributes } from "react";
// テレスとの対話欄でだけ使われる（ngraph.jp では表示されない）
export function Button({ size: _s, variant: _v, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { size?: string; variant?: string }) {
  return <button {...props} />;
}
