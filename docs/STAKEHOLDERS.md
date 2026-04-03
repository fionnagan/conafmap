# Stakeholders & Audience Briefs

Every design, feature priority, and copy decision should serve one of these four
audiences. When trade-offs arise, use this document to resolve them.

---

## 1. Fans (Primary Audience)

**Who they are:** Listeners of "Conan O'Brien Needs a Friend" who either called in
to the "Needs a Fan" segment or appeared on "Conan Must Go." Also: the broader fan
community who love the show and want to explore its universe.

**What they want:**
- Find themselves on the map ("Is my pin there? Does it show the right city?")
- Find fans near them geographically
- Share their pin with friends and on social media
- Explore who else is on the map and what they do
- Listen to the episode player directly in the popup
- Feel seen and celebrated — not just a data point

**Design implications:**
- The popup is the centerpiece — it should feel personal and warm, not database-y
- Shareable URLs are high priority (`?fan=episode-slug` feature)
- Mobile experience matters — fans discover this on their phones
- The episode audio player in every popup is non-negotiable
- Fan's question to Conan is a delightful detail fans care about
- "Find a fan near me" button would be widely used

**Copy tone for fans:** Warm, specific, celebratory. Not corporate.

---

## 2. Team Coco (Production Team)

**Who they are:** The producers, writers, and social media team behind the podcast.
They manage the show's online presence and want tools that make their work easier
and their content more shareable.

**What they want:**
- A living asset they can point press, guests, and distribution partners to
- Proof of the show's global geographic reach ("we have fans in 34 countries")
- To add a new fan episode in under 2 minutes without asking an engineer
- Something polished enough to embed on teamcoco.com or link in a press kit
- Data they can screenshot for social media posts ("Did you know our fans come from...")

**Design implications:**
- Embed mode (`?embed=1`) is high priority — strips header/footer for clean iframes
- The analytics section should be screenshot-worthy
- "Adding a fan" workflow must be dead simple (→ `docs/DATA_GUIDE.md`)
- The map should update in real time as new episodes air
- The header podcast logo and platform links serve as a mini marketing page

**Copy tone for Team Coco:** Professional, metrics-forward, brand-aligned.

---

## 3. HBO (Must Go Show)

**Who they are:** The network that produces and distributes "Conan Must Go," the travel
show where Conan visits fans in their home countries. HBO has its own marketing needs
for the show and wants the brand to be clearly represented.

**What they want:**
- Must Go fans clearly distinguished from podcast-only fans
- HBO brand color (`#0057B8` — HBO blue) used consistently for all Must Go elements
- Season distinction (Season 1 vs Season 2 badges) for clarity
- The map's geographic spread as a talking point for the show's international appeal
- Content that could live on HBO's own platforms or marketing materials

**Design implications:**
- Must Go pins are HBO blue, not orange — this is non-negotiable
- Season badges ("Must Go — S1", "Must Go — S2") must be visible in both popup and table
- The legend says "Also on Conan Must Go (HBO)" — the HBO attribution is intentional
- The analytics charts use HBO blue in the palette alongside TeamCoco orange
- The Continents chart (not just Countries) serves HBO's international-reach narrative
- Future: a "Must Go only" view or filter could be valuable for HBO's own use

**Copy tone for HBO:** Brand-conscious, internationally-minded.

---

## 4. Podcast Distributors (Apple, Spotify, Amazon Music, SiriusXM)

**Who they are:** The platforms that carry the podcast. Their marketing and partnerships
teams care about reach metrics. This map is a visual proof-of-concept that the show
has a genuinely global, diverse audience.

**What they want:**
- The analytics charts section (Top Countries, Continents, Occupations, Over Time)
- Data they can use in pitch decks or internal reports ("the show reaches X countries")
- Something they can screenshot cleanly without UI clutter
- Validation that their platform is featured prominently

**Design implications:**
- The analytics section should be self-contained and screenshot-worthy
- Export analytics as PNG is a direct distributor use case (future feature)
- Each distributor's logo and link appears in the header — maintaining this is important
- The "% World Nations" stat card speaks directly to distributors

**Copy tone for distributors:** Data-forward, professional, minimal.

---

## Priority Hierarchy for Trade-offs

When a feature or design decision benefits one audience at the expense of another,
use this order:

1. **Fans** — always first. This is ultimately a fan product.
2. **Team Coco** — they're the operators; their workflow needs must work.
3. **HBO** — brand consistency is a hard requirement, not a nice-to-have.
4. **Distributors** — analytics serve them but shouldn't compromise the fan experience.

**Example trade-off:** Making the analytics section wider/larger helps distributors
take better screenshots, but if it pushes the map below the fold on a fan's phone,
the fan experience loses. Fan wins — keep the map first, analytics below.

---

## Features by Stakeholder Value

| Feature | Fans | Team Coco | HBO | Distributors |
|---------|------|-----------|-----|--------------|
| Shareable pin URLs | ★★★ | ★★ | ★ | — |
| Find fan near me | ★★★ | ★ | — | — |
| Embed mode | ★ | ★★★ | ★★ | ★★ |
| Export analytics PNG | — | ★★ | ★ | ★★★ |
| Mobile bottom sheet | ★★★ | ★ | — | — |
| Choropleth layer | ★ | ★★ | ★★★ | ★★★ |
| Quick "add fan" workflow | — | ★★★ | — | — |
| Season filter (S1/S2) | ★★ | ★★ | ★★★ | — |
