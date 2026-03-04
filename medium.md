# Savings Plans: The Curve AWS Isn't Showing You

After 5 years managing Savings Plans and Reserved Instances for my firm, spending way too many hours on the AWS Console, I always had the feeling that something was missing from the recommendations AWS gives you.

When AWS announced Savings Plans for databases in 2025, I decided it was time to deep-dive this topic, replace doubts with certainty, and make the result available to everyone via an open-source Terraform module.

It turns out there's a curve — unique to your usage pattern and discount rate — that shows the exact relationship between how much you commit and how much you save. Where the sweet spot is, where returns decline, and where you start losing money. This is most likely what AWS uses to compute their recommendation, but they never show it to you, and they don't let you influence it.

## The problem with AWS recommendations

AWS Cost Explorer gives you a Savings Plans recommendation — one number, optimised for maximum savings over a lookback window. No usage distribution, no coverage percentage, no waste estimate, no way to set a target and work backwards. Just: "commit this much."

And it's a one-shot decision. No notion of splitting purchases over time, no current coverage context, no way to build an ongoing strategy. You should never make your full commitment in a single purchase — but that's exactly what the recommendation is designed for.

So when you need to answer real questions — "what if our load drops 20%?", "what's a safe commitment level?", "how bad is it if we don't use 100% of what we bought?" — you're on your own. You're committing 1 to 3 years of spending with incomplete information.

## Flexibility or extra savings?

Reserved Instances offer significantly higher discounts in theory, but they lock you to a Region and Instance Class, and now that the RI Marketplace is gone you can't offload the ones you don't need. EC2 Instance Savings Plans are essentially the same deal — 6 to 10 points more discount than Compute SPs, also locked to a region and instance family. Same rigidity, same complexity to manage, I ignored them for this reason.

With Compute SPs (EC2, Lambda, Fargate) and now Database SPs (RDS, Aurora, DynamoDB, ElastiCache), the two biggest chunks of most AWS bills can be covered by Savings Plans. You trade a few percentage points for flexibility — no lock-in, no transition plans. You commit to a dollar-per-hour spend and AWS applies it wherever it can. The only transition plan you'll ever need is when you decide to get off AWS — but that's a different article.

## What I built

After too many homemade scripts, it was time to turn this into a proper project: [terraform-aws-sp-autopilot](https://github.com/etiennechabert/terraform-aws-sp-autopilot), an open-source Terraform module that automates Savings Plans purchases with built-in strategy and reporting.

The module is composed of a set of three Lambda functions running on a schedule. But before talking about automation, let me start with what matters most: **visibility**.

### The report you wish AWS gave you

Every month, the module emails an HTML report that gives you what the console doesn't. For each SP type — Compute, Database, SageMaker — you get a stacked hourly usage chart showing how much of your spend is covered vs on-demand. You see the min, max, and distribution of your hourly usage. You see your current coverage and forecast future commitments.

![Savings Plans Coverage & Savings Report](medium/0.%20repport.png)

For each SP type, a link opens an [interactive simulator](https://etiennechabert.github.io/terraform-aws-sp-autopilot/) pre-loaded with your actual usage data and the current AWS recommendation. The simulator is a GitHub Pages app — you can try it right now, no install, no account needed.

### The simulator you dreamed about

The simulator can also be used standalone. Pick a built-in workload pattern (e-commerce, flat, batch, business-hours, random) or paste your own data.

![Workload Pattern & Cost Range](./medium/1.%20pattern-generator-loader.png)

Then you see the cost breakdown. For any commitment level, the simulator shows how your spend splits between covered (discounted rate), spillover (still on-demand rate), and wasted commitment (hours where you pay for more than you use). Two sliders let you adjust the commitment amount and savings percentage in real time. When opened from the report, the current AWS recommendation is included so you can see where AWS would put you.

One important detail: your savings percentage matters a lot, and you can't know yours until you have a first Savings Plan running. AWS recommendations for Database SPs assume around 20% — ours is actually 34.9%. Following the AWS recommendation with a 20% assumption would lead to a big overshoot. The simulator lets you plug in your real rate. Four strategy cards — Prudent, Min-Hourly, Balanced, Risky — give you reference points to compare.

![Cost Breakdown: Coverage vs Actual Usage](medium/2.%20cost-breakdown.png)

Below that, the savings-vs-commitment curve shows your net savings as a percentage of baseline cost, for every possible commitment level. Colour-coded: building to baseline, extra savings, declining savings, below baseline, losing money.

This curve is unique to you. It depends on your load pattern and your actual savings percentage, which varies by AWS product, instance type, and region. Two organisations with the same spend but different usage patterns will have very different curves. This is probably what AWS computes behind the scenes for their recommendation — they just don't show you the curve.

Look at how it flattens near the top. The last few percent of savings require much more commitment for less return. The sweet spot is almost never at the peak.

![Savings vs Commitment Level](medium/3.%20Savings-Commitement-level.png)

Now the big one: **what if our load drops?** The Load Factor slider lets you simulate a usage reduction — say -20% — and the whole curve recalculates.

This changed how I think about commitment. I used to believe you should keep a safe gap between your commitment and your min-hourly to avoid wasting money. The simulator showed me the opposite: being too cautious is actually how you waste money. When your load drops moderately, your spillover goes down while your wasted commitment stays small — you pay less overall. You only start losing when the drop is large enough that usage falls below your commitment.

For most workloads with some variance, the safety buffer already exists naturally — that's what the curve declining after the optimal point shows. You don't need to add one yourself. And this is even more true if you distribute purchases over time: every month you have plans expiring that you can simply choose not to renew.

![Savings vs Commitment Level — with a -20% load drop](medium/4.%20Load-drop.png)

### The automation

Once you have visibility and understand your usage, the automation is simple:

**A Scheduler** checks your current coverage via Cost Explorer, picks a purchase amount based on your strategy, and queues a purchase intent to SQS. Nothing is bought yet. It sends an email with what it plans to buy, inviting your team to review.

**A Review Window** — up to 14 days — lets you inspect or cancel queued purchases before they go through.

**A Purchaser** processes the queue, checks against your safety caps, and executes.

The module ships with three strategies. My recommended one:

- **Dichotomy**: exponential halving — starts big, slows as you approach the target. Over time your purchases get smaller, which means if your load drops you naturally adapt: you just buy less next month, or skip entirely. And when the first big purchases expire, they get replaced by smaller ones — your commitment gradually becomes more distributed and easier to adjust.

The other two:

- **Fixed**: buys a constant percentage each cycle, ramping linearly to your target. Predictable, easy to explain to finance.
- **Follow-AWS**: uses the AWS recommendation directly. Simple, but be careful — it can be aggressive.

You set **hard caps** — a max coverage ceiling and a max purchase per cycle — so the automation can never over-commit. Commitments are spread over time, not made in one shot. And there's a dry-run mode to watch what it would do before it spends anything.

## Try it

I built this on my own time so I could open-source it — I wanted anyone dealing with the same frustrations to benefit from what I learned. The easiest way to start is the [simulator](https://etiennechabert.github.io/terraform-aws-sp-autopilot/), go ahead, open it — plug in your numbers, play with the load factor, and see where your commitment actually sits on the curve. That alone might change how you think about your next purchase.

When you're ready for more, deploy the module with just the reporter — get monthly visibility on your real coverage, no automation yet. Then add the scheduler. The purchaser is the last step, and it's optional — some teams prefer to keep that button manual, and that's fine.

Either way, stop guessing.

---

*[terraform-aws-sp-autopilot](https://github.com/etiennechabert/terraform-aws-sp-autopilot) is open-source and on the Terraform Registry. Contributions and feedback welcome.*

*I'm always interested in discussing FinOps challenges — feel free to reach out if you want to chat about Savings Plans strategy or cloud cost optimisation in general.*
