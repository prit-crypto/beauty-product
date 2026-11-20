# Ask Dr. Beauty: concept demo for Dr. Beauty Care

A private demo storefront in Dr. Beauty Care's brand look (gold `#b5822d`, cream `#f7f7ed`, Cardo + Lato, her original
menu), with an AI shopping assistant built in. The client's own site (drbeautycare.org) is offline, so the catalogue
(49 products, AED 120–9,000) was rebuilt from the Internet Archive snapshot of Dec 2024.

**Concept demo only:** not affiliated with Dr. Beauty Care, no real orders, keep it private (see Deploy).

## What it does
- **Storefront:** home, 5 categories, product pages, cart with mock cash-on-delivery checkout.
- **Ask Dr. Beauty chat** (English and Arabic, RTL):
  - A short consultation leads to a morning and night routine from her products, fitted to the customer's budget, then a one-tap "add routine to cart".
  - **Safety gate on every message:** pregnancy, breastfeeding, medication, allergy, health conditions or children stop the selling and open a hand-off form for her team.
  - **Claims filter on every reply:** no "cure", "guaranteed", "stops hair loss" or "whitening".
- **Owner dashboard** at `/admin`: conversations, routines, cart value, orders, hand-offs waiting, top concerns, and an AI-mode switch.

### Conversation features
- **Memory:**
  - The customer's name, and the last 24 messages of the conversation.
  - What was just shown, so "the first one", "it" and "the mask" work.
  - The cart, sent from the browser.
  - The chat is restored after a page reload or a return visit. Use ↻ in the chat header to start a new one.
- **Basic abilities:**
  - Consultation and routine.
  - Recap ("what did you suggest?").
  - Remove a product from the routine ("skip the eye cream"). It stays out if the routine is rebuilt.
  - Add one product to the cart.
  - Compare products (a side-by-side table).
  - Browse with filters ("hair masks under 200").
  - Cart status.
  - Store questions: payment, delivery, returns, order status, offers, the founder, product origin. Answers come only from `data/faq.json`.
  - Ask for a real person (contact form).
  - Small talk.
- **Natural voice:** with Gemini or OpenAI and `AI_REWRITE=true`, the AI writes every reply from the conversation and the engine's facts. Safety hand-off messages always keep their fixed wording.

### Rules the engine enforces
- **Budget:**
  - A stated budget is a hard limit: the least important products are dropped until the routine fits.
  - Extras are shown only if they fit too.
  - "Minimal price" or "cheapest" gives the single most suitable affordable product.
  - "Best" never triggers the luxury line; only "premium" or "luxury" does.
- **Cart:**
  - The assistant can add one product, add the routine (never twice), remove a product, or empty the cart ("revert the order").
  - Every change is sent to the browser as a card and applied for real.
- **No invented actions:** the AI may only describe actions that actually happened this turn. A reply claiming "I've added", "I've cleared", "I've made sure"… when nothing happened is rejected, and the fixed wording is used instead.
- **Stays on topic:** off-topic requests (weather, poems), other brands and home remedies are politely declined.
- **No dead ends:** a question that goes unanswered twice gets a sensible default, so the chat never loops.

### Orders in the chat
- **Checkout:**
  - "Place my order", "checkout", or "yes" after the assistant offers to check out opens a cash-on-delivery form inside the chat.
  - Placing the order empties the cart, and the chat remembers the order.
  - Orders from the cart page are linked to the same conversation.
- **Order status:** "Where is my order?" answers with the order number, items, total and the phone number the team will call (last 4 digits only).
- **Cancel or change:** "Cancel my order" sends the request to the team with the customer's name and phone, so it appears in `/admin` as a hand-off. Before any order exists, it simply empties the cart.
- **History:** "Do you remember / my previous history?" summarises what the chat knows on this device (topic, routine, cart, orders), or says plainly that it's a new conversation.
- **Yes and no:**
  - "Yes", "OK" or "sure" answer the last question: add the routine just offered, add the product just shown, or check out. With nothing pending, they continue the consultation.
  - "No" leaves things as they are.
- **Adding by message:** right after a routine, "add this to my cart" or "add those" adds the whole routine. Naming a product ("add the shampoo") adds only that one. Nothing is added twice, and the reply says what was already there.
- **AI-only guesses can't wipe anything:** starting over, emptying the cart, cancelling or checking out need the customer's own words, never the AI's guess alone.

### Relevant suggestions only
- **Every product is chosen for a reason.** It's suggested only when one of its verified concern tags matches a concern the customer stated. The card shows that reason ("For: Dandruff").
- **The tags were checked.** They were reviewed against each product's real store description (`scripts/audit_catalog.py` writes `data/catalog_audit.json`).
- **Two products are never suggested:** Brazilian Cleopatra and Oily Extra Power Protein, whose store pages have no description.
- **Budget cuts keep every concern covered:** products whose concern another product already covers are dropped first.
- **Hair rules:**
  - A medicated wash (dandruff or hair fall) comes first, with a second wash for curls on alternate days.
  - The straightening treatment is never suggested for curly hair.
  - "Premium" for hair adds only relevant products within the budget, and says that the luxury Cana Gold line is skincare.
- **Gaps are said plainly:** "We don't have a product for …". Needs the range doesn't cover (`data/unsupported.json`: sunscreen, acne, face wash, feet, etc.) get the same honest answer. An alternative is offered only if a real product fits, and it's labelled.
- **No invented concerns:** the AI must quote the customer's own words for every concern it reads, and anything without a real quote is dropped. The AI also can't add to the cart on its own reading.

### Consultation questions (dynamic)
The assistant asks only the questions whose answer changes the products, and skips any the customer already answered.
They are defined in `backend/app/engine/questions.py`.

| Area | Question | Asked when | What the answer changes |
| --- | --- | --- | --- |
| Skin | Skin type: dry / oily / combination / normal | dryness or oiliness not mentioned yet | dry adds moisture products; oily or combination adds the pore toner |
| Skin | Sensitive? | the routine would include the exfoliant or the peel | sensitive leaves them out (and says so), plus a patch-test tip |
| Skin | Essentials or complete routine? | the routine has 3 or more products that overlap | essentials keeps one product per concern; the rest become optional extras |
| Hair | Straight / wavy / curly | curls not mentioned yet | curly adds the curl wash and never a straightening treatment |
| Hair | Scalp: dandruff / hair fall / fine | no scalp concern yet | switches to the medicated Cystiphane wash |
| Hair | Coloured or bleached? | dry, damaged or frizzy hair | colour-safe wash and mask |
| Supplements | Pregnant, breastfeeding, under 18 or on medication? | always, before any supplement | yes goes to Dr. Shaymaa's team |

How the questions behave:
- **Limits:** at most 3 of these per consultation. A detailed first message (two or more concerns, or a budget) skips them, except the supplement safety check.
- **Answers:** a button or typed words, in English or Arabic ("it's curly", "مموج", "لا مو مصبوغ"). "Not sure" is always accepted. An unclear answer is asked once more, then skipped.
- **"Anything else?" step:** "nothing else", "that's all", "بس كذا" or "لا" moves on.
- **Wording:** with Gemini or OpenAI, the AI adds a short reaction to what the customer said, but the question itself is never reworded, so it always matches its buttons.

### Off-topic, side questions and bypass attempts
- **Off-topic** (weather, sport, coding, poems, "ignore your instructions", requests for other customers' data): a polite no, the list of what the assistant can do (in full the first time), then straight back to the pending question or offer.
- **Side questions keep your place:** a delivery question or "hi" in the middle of the consultation is answered, then the same question comes back with its buttons, and a pending "Shall I add…?" still works with "yes".
- **Short first messages get a short consultation:** "how can I be fair?" asks what else to work on, then sensitivity, then budget. Detailed messages (two or more concerns, or a budget) go straight to a routine.
- **Skin colour:** requests to be "fair" or "whiter" get an honest note: the products don't change natural skin colour; they brighten and even out the look of dark spots and dullness.
- **Under 18** ("I'm 16", "عمري 15") goes to Dr. Shaymaa's team like other safety topics.
- **Prices can't be changed:** the server reprices every cart and order from the catalogue, so a tampered browser request can't buy at a different price. "Set the price to AED 1" is answered with the real price.
- **Other brands** are never compared or judged; "budget 5 AED" is told the range starts at AED 120; "cancel my order" with no order asks before emptying the cart.

### Debug a conversation
`MODE=gemini PYTHONPATH=. .venv/bin/python scripts/replay.py < conversation.txt` replays a chat (typed lines and `btn:<action>|<label>` clicks) against a simulated cart, and prints every decision.

### Gemini settings (paid key)
`GEMINI_MODEL=gemini-3.8-flash` with `GEMINI_THINKING=low` gives about 2.5 s per AI call. Benchmarked: thinking set to low is about 3x faster than the default, with the same accuracy. Backups are `gemini-3.5-flash`, then `gemini-3.5-flash-lite`. The AI sees the last 30 messages, and each conversation keeps up to 80.

### Language switch
The EN / ع button in the chat header switches the same conversation, including its routine, cart and buttons, to the other language. It doesn't start a new chat. Typing in Arabic also switches automatically.

### Product photos
30 of 49 products have real photos, saved in `frontend/public/products/`:
- **Luxliss and IvyBears:** from the brands' official sites.
- **Cystiphane:** from Bailleul's site and Gulf pharmacies.
- **Cana Gold:** from archived copies of the brand's site.

Sources are listed in `backend/data/product_image_sources.json`. These photos belong to their brands, so use them only in the private demo. No photos could be found for Naturally No.1 or the Brazilian protein treatments; those need photos from the shop itself.

`scripts/fetch_product_images.py` downloads, checks and resizes photos from a JSON list of image URLs.
- **To add one:** save it as `frontend/public/products/<product id>.jpg` (or `.png` / `.webp`), for example `nn1-day-cream.jpg`, then restart the backend.
- **Where it appears:** on the shop pages and in the chat cards. Until then, the gold "DR" placeholder is shown.
- **Product IDs:** listed in `backend/data/catalog.json`.

Separate build folder: `NEXT_DIST_DIR=.next-e2e` builds and runs a second copy (for example tests on other ports) without touching the main `.next`.

## Portable AI layer
| `AI_PROVIDER` | What runs | Needs |
| --- | --- | --- |
| `rule` (default) | Keyword understanding + templates. Fully predictable, works offline | nothing |
| `gemini` | Gemini reads free text and re-words replies | `GEMINI_API_KEY` (model: `GEMINI_MODEL`, default `gemini-3.5-flash-lite`; `gemini-2.5-flash` is closed to new accounts) |
| `openai` | OpenAI (or any compatible endpoint) does the same | `OPENAI_API_KEY` (model: `OPENAI_MODEL`, `OPENAI_BASE_URL`) |

In every mode the **deterministic engine** picks products, prices and totals, and runs the safety gate. The AI only:
- reads free text into structured fields, and
- re-words the reply.

AI wording is rejected if it contains a number that isn't in the facts. Any AI error or timeout falls back to `rule`
automatically, and after a failure the AI is skipped for 30 seconds so the chat stays fast.

`AI_REWRITE=false` keeps the AI for understanding messages and answering questions, but uses the fixed templates for
routine replies. With Gemini that is about 3.5 s instead of about 6 s per routine reply. The mode can also be switched live from `/admin` when keys are set.

## Run locally
```bash
# backend (Python 3.11+)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # set AI_PROVIDER and keys if you want gemini/openai
.venv/bin/uvicorn app.main:app --port 8000

# frontend (Node 20+)
cd frontend
npm install
npm run dev                     # http://localhost:3000 ; /api is proxied to the backend
```
Owner dashboard: http://localhost:3000/admin (password = `ADMIN_PASSWORD`, default `drbeauty-demo`).

## Tests
```bash
cd backend && .venv/bin/python -m pytest -q        # engine, safety, claims, providers, API, 5 demo scripts
cd frontend && npx playwright test                  # browser smoke tests (uses installed Google Chrome; servers running)
```
Live Gemini/OpenAI tests run automatically when `GEMINI_API_KEY` / `OPENAI_API_KEY` are set.

## Demo script (for the pitch)
1. English: *"I'm 38, I have fine lines around my eyes and my skin feels dull. Budget around AED 900."*
   - To stay within AED 900 it keeps one product per concern: Day Cream (fine lines), Brightening Cream (dull skin) and Under Eye Cream (dark circles), **AED 887**. Each card line says what the product is for.
   - Then "Add routine to cart".
2. Arabic (tap ع): *"شعري جاف ومنفوش بعد الصبغة، ماذا أستخدم؟"*
   - A wash for the frizz, the argan mask for dry, colour-treated hair, and the argan serum, shown right-to-left with Arabic product descriptions.
3. *"Can I take Cystiphane tablets while breastfeeding?"*: a hand-off form appears, with no product suggested.
4. *"Will this cure my hair loss?"*: the assistant declines the claim and explains what the shampoo is designed to do.
5. *"Do you have sunscreen?"*: the assistant says plainly it isn't in the range, and doesn't push something else.
6. Open `/admin`: the chats, cart value, the waiting hand-off and the top concerns are all there.
7. Pitch talking point: her homepage promised cleansers and sunscreens, but the range has none. Every routine tip
   mentions both, which opens a conversation about new co-branded products.

## Data and rules you can edit
- `backend/scripts/build_catalog.py`: product curation (line, routine step, concern tags, safe one-line summaries). Run it to rebuild `data/catalog.json`.
- `backend/data/concerns.json`: concern labels and English/Arabic keywords.
- `backend/data/safety_terms.json`: topics that trigger a hand-off.
- `backend/data/blocked_terms.json`: claims rewritten to safer wording.
- `backend/app/engine/recommender.py`: which product fills which routine step, and the budget-dropping priority.
- `backend/app/engine/templates.py`: every reply in English and Arabic.

These lists are our draft. They should be validated by Dr. Shaymaa or her regulatory adviser before any real use.

## Product images
The archive kept no product photos, so the cards use brand-styled placeholders (with the Cana Gold and IvyBears
logos). To add photos:
1. Put the files in `frontend/public/products/`.
2. Set each product's `image` field (for example `"/products/nn1-day-cream.jpg"`) in `catalog.json`.

## Deploy (private)
- **Frontend:**
  - Set `API_URL` to the backend's URL.
  - Set `DEMO_BASIC_AUTH="user:password"` to put the whole site, including `/api`, behind basic auth.
  - Pages already send `noindex`.
- **Backend:** run with uvicorn behind your proxy. Keep it reachable only from the frontend if possible.
