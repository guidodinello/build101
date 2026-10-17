# Competitive landscape: evidence

Evidence behind [competitors.md](../competitors.md). Read 2026-10-17 via web search; most sources are vendor blogs or affiliate comparisons, so product claims are unverified unless noted.

## Meta Business Agent (customer-facing)

- Generally available since June 2026. It answers product questions from the business's catalog, books appointments, qualifies leads and closes sales in the chat, handing off to humans at points the business sets ([WhatsApp Business blog](https://whatsappbusiness.com/blog/introducing-meta-business-agent-ai/), [Omnichat](https://blog.omnichat.ai/meta-business-agent-platform-explained-features-pricing-and-what-the-2026-whatsapp-changes-mean-for-your-business/)).
- Reportedly used by over a million businesses on WhatsApp or Messenger; set up from the WhatsApp Business app without a developer ([Omnichat](https://blog.omnichat.ai/meta-business-agent-platform-explained-features-pricing-and-what-the-2026-whatsapp-changes-mean-for-your-business/)).
- **Takeaway:** it talks to the business's customers, not to the owner. Complementary, not a substitute: it sells, we market and (later) run the back office.

## "AI employees": Sintra, Marblism, Lindy (owner-facing, dashboard-first)

- **Sintra** sells pre-built, role-based helpers (12 per its own blog), each with a name, character art and a role description, e.g. Milli (sales), Buddy (business development), Cassie (support) ([Sintra blog](https://sintra.ai/blog/best-ai-employees); direct observation of sintra.ai, 2026-10-17). A competitor's comparison criticizes its helpers for stopping at suggestions ([lowcode.agency](https://www.lowcode.agency/blog/marblism-vs-lindy-vs-motion-ai)). Entry price ranges from about $15.60/mo to $97/mo depending on source and bundle ([Sintra blog](https://sintra.ai/blog/best-ai-employees), [layer3labs](https://www.layer3labs.io/guides/ai-employee-platforms-compared)).
- **Marblism** pitches "AI employees to scale your business" that "run your inbox, socials, SEO, lead generation, calls, and support"; claims 40,000+ businesses. Its social media employee "Sonny" watches what goes viral and creates on-brand photos and videos (direct observation of marblism.com, 2026-10-17). About $24/mo entry ([crevio review](https://crevio.co/blog/marblism-review)).
- **Lindy** is a general-purpose agent builder for email, calendar and admin; about $30–50/mo, usage-based ([lowcode.agency](https://www.lowcode.agency/blog/best-ai-employee-platforms-for-small-business), [Lindy blog](https://www.lindy.ai/blog/sintra-ai-pricing)).
- One guide estimates one to three weeks of setup before an AI employee performs reliably ([layer3labs](https://www.layer3labs.io/guides/ai-employee-platforms-compared)).
- **Takeaway:** the closest competitors on the marketing job (Marblism's Sonny, Sintra's social helper). Their named, illustrated roles are worth copying; their cast of 6–12 characters to manage is not, for a non-technical owner. We keep one face (the account manager) and show the team working behind it ([conversation-design.md](../product/conversation-design.md), [ADR 0006](../decisions/0006-fixed-agent-catalog-brand-brain.md)).

## Shopify Sidekick (owner-facing, platform-locked)

- Conversational agent over Shopify's internal APIs that shows changes for approval before applying them; desktop and mobile, text, voice and screen sharing ([chattergo](https://www.chattergo.com/blog/shopify-sidekick-deep-dive-from-chatbot-to-agentic-copilot), [ringly](https://www.ringly.io/blog/ai-sidekick-shopify)). Third-party blogs, not Shopify docs.
- **Takeaway:** validates approve-before-apply for owners ([ADR 0007](../decisions/0007-approve-every-post.md)); only for Shopify merchants.

## LatAm WhatsApp sales agents (customer-facing)

- **Leadsales** launched an AI sales agent for WhatsApp SMEs; official Meta Business Partner ([Mexico Business News](https://mexicobusiness.news/cloudanddata/news/leadsales-launches-ai-sales-agent-whatsapp-smes)).
- **Yavendio**: WhatsApp commerce agents, 7,000+ customers, expanding from Peru to Brazil ([Northflank case study](https://northflank.com/blog/yavendio-scaled-ai-powered-whatsapp-commerce-across-latam-with-northflank)).
- **Agenteala** (Buenos Aires): connects to CRM, inventory and payments; from $49/mo for 5K messages ([agenteala.com](https://agenteala.com/en/)).
- **Wa2Desk**, **Aurora Inbox**: agents trained on catalog and brand voice ([wa2desk.ai](https://wa2desk.ai/en), [Aurora Inbox](https://www.aurorainbox.com/en/whatsapp-sales-for-smes/)).
- **Takeaway:** the region already pays for WhatsApp AI, but every one of these faces the customer.

## Personal agents over messaging

- **Poke** ([poke.com](https://poke.com), The Interaction Company of California): personal assistant in iMessage, SMS, Telegram and, in some markets, WhatsApp; handles email, calendar, reminders. Its defining trait is proactivity: it watches connected services and writes first ([TechCrunch](https://techcrunch.com/2026/04/08/poke-makes-ai-agents-as-easy-as-sending-a-text/)). Cognition is acquiring the company ([runtimewire](https://runtimewire.com/article/cognition-acquires-poke-interaction-consumer-ai-agents)). Its WhatsApp support is limited by Meta's 2026 chatbot policy ([TechCrunch](https://techcrunch.com/2026/04/08/poke-makes-ai-agents-as-easy-as-sending-a-text/)).
  - Not to be confused with **Pokee** ([pokee.ai](https://pokee.ai/blog/pokee-vs-chatgpt)), an agent platform for professionals and enterprises; not in our segment.
- **OpenClaw**: open-source, self-hosted agent connected to the user's messaging apps; 347K GitHub stars by April 2026 ([MindStudio](https://www.mindstudio.ai/blog/what-is-openclaw-ai-agent)).
- **Takeaway:** Poke is the reference for the "someone who texts me first" feel. Our proactive weekly plan message is that pattern for marketing.

## WhatsApp policy (context for every row above)

- Since 2026-01-15, Meta bars AI providers from the WhatsApp Business API when the assistant is the core product (ChatGPT, Perplexity left); business-specific bots (support, bookings, sales, notifications) remain allowed, and Meta decides what counts as primary use ([respond.io](https://respond.io/blog/whatsapp-general-purpose-chatbots-ban), [Business Standard](https://www.business-standard.com/technology/tech-news/meta-bans-ai-chatbots-from-whatsapp-business-api-chatgpt-to-shut-down-jan-2026-125102200335_1.html)). Tracked in [open-questions.md](../open-questions.md#channel--platform-risk).

## Gap found

No result described an assistant that takes the **owner's** instructions over WhatsApp and acts for the business (searched 2026-10-17; customer-facing bots dominate). Positioning line that falls out of it:

> Sintra gives you a team you have to manage. We give you one person who manages the team for you.
