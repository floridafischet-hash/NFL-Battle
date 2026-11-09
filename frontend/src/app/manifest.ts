import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "NFL Bracket Battle",
    short_name: "Bracket Battle",
    description: "Das private NFL-Playoff-Tippspiel",
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#04060c",
    theme_color: "#04060c",
    lang: "de",
    categories: ["sports", "entertainment"],
    prefer_related_applications: false,
    shortcuts: [
      { name: "Aktuelle Spiele", short_name: "Spiele", url: "/aktuelle-spiele", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "NFL Teams", short_name: "Teams", url: "/teams", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Chat", short_name: "Chat", url: "/chat", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
