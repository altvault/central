import { Hono } from "hono";
import { basicAuth } from "hono/basic-auth";
import { HTTPException } from "hono/http-exception";
import { validator } from "hono/validator";

import config from "../../config.json";

const app = new Hono<{ Bindings: CloudflareBindings }>();

app.use(
  "/*",
  // Basic Auth Middleware
  async (c, next) => {
    if (!c.env.WORKER_USERNAME || !c.env.WORKER_PASSWORD) {
      return c.json({ error: "Server configuration error" }, 500);
    }
    const auth = basicAuth({
      username: c.env.WORKER_USERNAME,
      password: c.env.WORKER_PASSWORD,
    });
    return await auth(c, next);
  },
);

app.get(
  "/download/:repo/:asset_id/:name?",
  validator("param", (value) => {
    const { repo, asset_id } = value;
    if (!/^[A-Za-z0-9_.-]+$/.test(repo) || !/^\d+$/.test(asset_id)) {
      throw new HTTPException(400);
    }
    return { repo, asset_id };
  }),
  async (c) => {
    const { repo, asset_id } = c.req.valid("param");
    const token = c.env.WORKER_GITHUB_TOKEN;

    const response = await fetch(
      `https://api.github.com/repos/${config.owner}/${repo}/releases/assets/${asset_id}`,
      {
        headers: {
          Accept: "application/octet-stream",
          Authorization: `Bearer ${token}`,
          "User-Agent": "Worker",
          "X-GitHub-Api-Version": "2026-03-10",
        },
        redirect: "manual",
      },
    );

    const location = response.headers.get("Location");
    if (location) {
      return c.redirect(location, 302);
    }
    throw new HTTPException(502);
  },
);

app.get("/:name{.+\\.json}", async (c) => {
  const { name } = c.req.param();
  const token = c.env.WORKER_GITHUB_TOKEN;

  const response = await fetch(
    `https://api.github.com/repos/${config.owner}/${config.index_repo}/releases/tags/${config.index_tag}`,
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "User-Agent": "Worker",
        "X-GitHub-Api-Version": "2026-03-10",
      },
    },
  );

  if (!response.ok) throw new HTTPException(502);
  const data = (await response.json()) as {
    assets?: Array<{
      id: number;
      name: string;
      url: string;
    }>;
  };
  const asset = data.assets?.find((x) => x.name === name);
  if (!asset) throw new HTTPException(404);
  const json_response = await fetch(asset.url, {
    headers: {
      Accept: "application/octet-stream",
      Authorization: `Bearer ${token}`,
      "User-Agent": "Worker",
      "X-GitHub-Api-Version": "2026-03-10",
    },
    redirect: "follow",
  });
  if (!json_response.ok) throw new HTTPException(502);
  const json = (await json_response.json()) as {
    iconURL: string;
    apps: Array<{ downloadURL: string; iconURL: string }>;
  };
  // Modifications
  json.iconURL = new URL(json.iconURL, c.req.url).toString();
  json.apps.forEach((x) => {
    const downloadURL = new URL(x.downloadURL, c.req.url);
    downloadURL.username = c.env.WORKER_USERNAME;
    downloadURL.password = c.env.WORKER_PASSWORD;
    x.downloadURL = downloadURL.toString();
    const iconURL = new URL(x.iconURL, c.req.url);
    x.iconURL = iconURL.toString();
  });
  return c.json(json);
});

export default app;
