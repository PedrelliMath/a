#!/usr/bin/env bun
// Local-dev build script — injeta APP_HOST/APP_PORT/KEYCLOAK_PORT no bundle.
// Use junto com APP_HOST=localhost APP_PORT=18000 KEYCLOAK_PORT=8080 antes do comando.
import plugin from "bun-plugin-tailwind";
import { existsSync } from "fs";
import { rm } from "fs/promises";
import path from "path";

const APP_HOST = process.env.APP_HOST || "localhost";
const APP_PORT = process.env.APP_PORT || "18000";
const KEYCLOAK_PORT = process.env.KEYCLOAK_PORT || "8080";

const outdir = path.join(process.cwd(), "dist");
if (existsSync(outdir)) {
  await rm(outdir, { recursive: true, force: true });
}

const entrypoints = [...new Bun.Glob("**.html").scanSync("src")]
  .map((a) => path.resolve("src", a))
  .filter((dir) => !dir.includes("node_modules"));

const result = await Bun.build({
  entrypoints,
  outdir,
  plugins: [plugin],
  minify: true,
  target: "browser",
  sourcemap: "linked",
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
    "process.env.APP_HOST": JSON.stringify(APP_HOST),
    "process.env.APP_PORT": JSON.stringify(APP_PORT),
    "process.env.KEYCLOAK_PORT": JSON.stringify(KEYCLOAK_PORT),
  },
});

console.log("outputs:", result.outputs.map((o) => path.basename(o.path)));
console.log(
  `injected: APP_HOST=${APP_HOST} APP_PORT=${APP_PORT} KEYCLOAK_PORT=${KEYCLOAK_PORT}`,
);