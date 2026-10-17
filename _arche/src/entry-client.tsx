import { hydrateRoot } from "react-dom/client";
import { App, type PageProps } from "./app";
import "./arche.css";

const root = document.getElementById("arche-root");
if (root) {
  const slug = root.dataset.slug;
  const props: PageProps = slug ? { kind: "detail", slug } : { kind: "list" };
  hydrateRoot(root, <App {...props} />);
}
