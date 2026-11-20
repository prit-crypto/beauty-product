import { expect, test } from "@playwright/test";

// Run against the backend in rule mode (AI_PROVIDER=rule) so the wording is predictable.

async function openChat(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Open Ask Dr. Beauty chat" }).click();
  const chat = page.getByRole("region", { name: "Ask Dr. Beauty chat" });
  await expect(chat.getByRole("button", { name: "Skin" }).or(chat.getByText(/again|Hi again/))).toBeVisible();
  return chat;
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test("demo script 1: English routine within AED 900 lands in the cart at AED 887", async ({ page }) => {
  const chat = await openChat(page);
  await chat.getByRole("textbox").fill("I'm 38, I have fine lines around my eyes and my skin feels dull. Budget around AED 900.");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(chat.getByText("Total: 887 د.إ")).toBeVisible();
  await chat.getByRole("button", { name: "Add routine to cart" }).first().click();
  await expect(chat.getByText(/\(AED 887\) (to|in) your cart/)).toBeVisible();
  await page.goto("/cart");
  await expect(page.getByText("887 د.إ").first()).toBeVisible();
});

test("demo script 3: breastfeeding question hands off with a contact form", async ({ page }) => {
  const chat = await openChat(page);
  await chat.getByRole("textbox").fill("Can I take Cystiphane tablets while breastfeeding?");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(chat.getByText("Talk to Dr. Shaymaa's team")).toBeVisible();
  await chat.getByPlaceholder("Name").fill("Sara");
  await chat.getByPlaceholder("Phone number").fill("+971500000000");
  await chat.getByRole("button", { name: "Send to the team" }).click();
  await expect(chat.getByText(/Thank you, Sara/)).toBeVisible();
});

test("the conversation comes back after a page reload", async ({ page }) => {
  const chat = await openChat(page);
  await chat.getByRole("textbox").fill("show me hair masks under 200");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(chat.getByText("Luxliss Argan Oil Intensive Moisture Mask")).toBeVisible();
  await page.reload();
  const again = await page
    .getByRole("button", { name: "Open Ask Dr. Beauty chat" })
    .click()
    .then(() => page.getByRole("region", { name: "Ask Dr. Beauty chat" }));
  await expect(again.getByText("show me hair masks under 200")).toBeVisible();
  await expect(again.getByText("Luxliss Argan Oil Intensive Moisture Mask")).toBeVisible();
});

test("compare and add from the comparison table", async ({ page }) => {
  const chat = await openChat(page);
  await chat.getByRole("textbox").fill("What's the difference between the day cream and the night cream?");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(chat.getByRole("table")).toBeVisible();
  await chat.getByRole("table").getByRole("button", { name: "Add" }).first().click();
  await expect(chat.getByText(/in your cart|to your cart/).last()).toBeVisible();
});

test("budget is kept and cart edits really happen", async ({ page }) => {
  const chat = await openChat(page);
  const say = async (m: string) => {
    await chat.getByRole("textbox").fill(m);
    await chat.getByRole("button", { name: "Send" }).click();
  };
  await say("my skin is dry and has dark spots, budget 300 AED");
  await expect(chat.getByText("Total: 269 د.إ")).toBeVisible();
  await chat.getByRole("button", { name: "Add routine to cart" }).first().click();
  await expect(page.getByRole("link", { name: /Cart, 1 items/ })).toBeVisible();
  await say("Remove the current products from my cart.");
  await expect(page.getByRole("link", { name: /Cart, 0 items/ })).toBeVisible();
});

test("add the routine by message, check out in the chat, then ask about the order", async ({ page }) => {
  const chat = await openChat(page);
  const say = async (m: string) => {
    await chat.getByRole("textbox").fill(m);
    await chat.getByRole("button", { name: "Send" }).click();
  };
  await say("my hair is dry and colour-treated, budget 300 AED");
  await expect(chat.getByText("Total: 270 د.إ")).toBeVisible();
  await say("Add this to my cart.");
  await expect(page.getByRole("link", { name: /Cart, 2 items/ })).toBeVisible();
  await say("Can you add those again please?");
  await expect(chat.getByText(/Already in your cart/)).toBeVisible();
  await expect(page.getByRole("link", { name: /Cart, 2 items/ })).toBeVisible();
  await say("place my order");
  await chat.getByPlaceholder("Full name").fill("Huda Ali");
  await chat.getByPlaceholder(/Phone/).fill("+971501234567");
  await chat.getByRole("button", { name: /Place order/ }).click();
  await expect(chat.getByText(/Your order #\d+ \(AED 270\) is placed/)).toBeVisible();
  await expect(page.getByRole("link", { name: /Cart, 0 items/ })).toBeVisible();
  await say("where is my order?");
  await expect(chat.getByText(/has been received/)).toBeVisible();
});


test("switching language keeps the chat, shows a divider and no fake message", async ({ page }) => {
  const chat = await openChat(page);
  await chat.getByRole("textbox").fill("my hair is curly and frizzy");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(chat.getByText(/Total:/)).toBeVisible();
  await chat.getByRole("button", { name: "ع" }).click();
  await expect(chat.getByRole("separator").filter({ hasText: "العربية" })).toBeVisible();
  await expect(chat.getByText("بكل سرور، سنكمل بالعربية.", { exact: false })).toBeVisible();
  await expect(chat.locator("p.bg-ink", { hasText: "العربية" })).toHaveCount(0);
});

test("a placed order stays placed after closing and reopening the chat (and after a reload)", async ({ page }) => {
  const chat = await openChat(page);
  await chat.getByRole("textbox").fill("tell me about the day cream");
  await chat.getByRole("button", { name: "Send" }).click();
  await chat.getByRole("button", { name: "Add" }).first().click();
  await expect(page.getByRole("link", { name: /Cart, 1 items/ })).toBeVisible();
  await chat.getByRole("textbox").fill("place my order");
  await chat.getByRole("button", { name: "Send" }).click();
  await chat.getByPlaceholder("Full name").fill("Test");
  await chat.getByPlaceholder(/Phone/).fill("+971501234567");
  await chat.getByRole("button", { name: /Place order/ }).click();
  await expect(chat.getByText(/is placed/)).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Open Ask Dr. Beauty chat" }).click();
  const again = page.getByRole("region", { name: "Ask Dr. Beauty chat" });
  await expect(again.getByText(/is placed/)).toBeVisible();
  await expect(again.getByText("✓ Order placed")).toBeVisible();
  await expect(again.getByRole("button", { name: /Place order/ })).toHaveCount(0);
});

test("browsing products offers next steps, not the Skin / Hair / Supplements buttons", async ({ page }) => {
  const chat = await openChat(page);
  await expect(chat.getByText(/Pregnant, breastfeeding, on medication/)).toBeVisible();
  await chat.getByRole("textbox").fill("show me hair products");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(chat.getByRole("button", { name: "Help me choose a hair routine" })).toBeVisible();
  await expect(chat.getByRole("button", { name: "Supplements", exact: true })).toHaveCount(0);
});

test("after adding the routine, its buttons show it's in the cart and the usage answer has no buy buttons", async ({ page }) => {
  const chat = await openChat(page);
  await chat.getByRole("textbox").fill("my skin is dry and has dark spots, budget 1000");
  await chat.getByRole("button", { name: "Send" }).click();
  await chat.getByRole("button", { name: /Add routine to cart ·/ }).click();
  await expect(chat.getByRole("link", { name: /Routine is in your cart/ })).toBeVisible();
  await chat.getByRole("textbox").fill("When should I use what thing in my routine?");
  await chat.getByRole("button", { name: "Send" }).click();
  await expect(chat.getByText("Here's how to use your routine:")).toBeVisible();
  await expect(chat.getByRole("button", { name: "Add routine to cart", exact: true })).toHaveCount(0);
  await expect(chat.getByRole("button", { name: "Show premium option" })).toHaveCount(0);
});

test("New chat (↻) forgets the old conversation, even if pressed while a reply is still coming", async ({ page }) => {
  const chat = await openChat(page);
  const say = async (m: string) => {
    await chat.getByRole("textbox").fill(m);
    await chat.getByRole("button", { name: "Send" }).click();
  };
  await say("Hi, I'm Layla. my skin is dry and has dark spots, budget 300 AED");
  await expect(chat.getByText("Total: 269 د.إ")).toBeVisible();
  // the next reply is slow; ↻ is pressed before it arrives
  await page.route("**/api/chat", async (route) => {
    if ((route.request().postData() || "").includes("cheaper please")) await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await say("cheaper please");
  await chat.getByRole("button", { name: "New chat" }).click();
  await page.waitForTimeout(2000); // the old reply has arrived by now and must be ignored
  await expect(chat.getByText("Total: 269 د.إ")).toHaveCount(0);
  await expect(chat.getByText(/lighter|simpler|cheaper/i)).toHaveCount(0);
  await say("what did you suggest?");
  await expect(chat.getByText("We haven't built a routine yet", { exact: false })).toBeVisible();
  await expect(chat.getByText(/Layla/)).toHaveCount(0);
});
