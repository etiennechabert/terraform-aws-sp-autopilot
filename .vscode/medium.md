# You Don't Know How to Use AWS Savings Plans

I came to this realisation while building an open-source Terraform module to manage Savings Plans automatically. After 5 years managing Savings Plans and Reserved Instances for my firm, spending way too many hours on the AWS Console staring at recommendations and coverage reports, I had to admit I was making commitment decisions without understanding the full picture.

And I'm pretty sure you are too.

## The end of the RI era

For a long time, Reserved Instances were the way to reduce your AWS bill. They still offer slightly higher discount rates than Savings Plans, but in practice they're a nightmare to manage. You commit on a specific Region and Instance Class, and when AWS launches a new generation or your product evolves, you're stuck building transition plans and juggling expiring reservations. Now that the RI Marketplace is gone, you can't even offload the ones you don't need.

Then AWS launched Savings Plans for databases — RDS, Aurora, DynamoDB, ElastiCache. This was the tipping point. With Compute SPs (EC2, Lambda, Fargate) already available and now Database SPs, the two biggest chunks of most AWS bills can be covered by Savings Plans.

SPs trade a few percentage points of savings for flexibility. No region lock-in, no instance class commitment, no transition plans. You commit to a dollar-per-hour spend and AWS applies it wherever it can. The only transition plan you'll ever need is when you decide to get off AWS — but that's a different article.

A note on EC2 Instance Savings Plans: they offer roughly 6 to 10 percentage points more discount than Compute SPs, but they lock you to a specific region and instance family, don't cover Lambda or Fargate, and can't be modified after purchase. The discount is actually the same as Standard RIs, with the same lack of flexibility. They're much more complex to manage — arguably the kind of thing you'd need a provider for (more on that below). I like simple things, so I ignored them in this module.

## The hidden problem with AWS recommendations

AWS Cost Explorer gives you a Savings Plans recommendation — a single hourly commitment amount, optimised for maximum savings over a lookback window. It looks precise. But try to understand what you're actually buying.

It doesn't show your hourly usage distribution — the min, median, or peak of your spend over time. It doesn't tell you what coverage percentage you'll reach if you follow it. It doesn't let you set a target coverage and work backwards. It doesn't show waste — how many hours your commitment would exceed your actual usage. And it doesn't tell you what happens if your load drops next quarter.

One number. No sensitivity analysis, no risk profile. As soon as your workload fluctuates — auto-scaling, batch jobs, business-hours patterns, basically using the cloud for what it's good at — that number becomes misleading.

AWS added a Purchase Analyzer in late 2024 that lets you try custom amounts and see the impact. But it's manual trial-and-error, not a strategy tool.

There's also a more basic issue: **you should never make your full commitment in a single purchase**. Distributing commitments over time smooths out usage fluctuations, avoids locking everything to the same expiry date, and lets you adjust as your workload evolves. But the AWS recommendation gives you a lump-sum number with no notion of current coverage, target coverage, or how to split purchases across months. It's built around a single decision, not an ongoing strategy.

When you try to answer the questions that actually matter, you're stuck:

- **"What happens if our load drops 20% — when do we start losing money?"**
- **"If we don't use 100% of the plans we bought, how bad is it?"**
- **"Should we target the same coverage for 1-year and 3-year commitments?"**
- **"What's a safe commitment level for our usage patterns?"**

You're committing your organisation to 1 or 3 years of fixed spending with incomplete information.

## The outsourcing option

You can hand the problem to a service provider. We did this for a while, and I want to be fair — the people we worked with were great. Clear, pedagogical, and they delivered the savings they promised.

But over time the downsides showed up. You never really understand the underlying problem. The provider handles the complexity, your team never learns, you create a dependency. When you decide to move on, you start from scratch.

The economics are also a wash. The extra savings they get from complex instruments — RIs, convertible RIs, instance-level optimisations — end up paying their margin. If you'd used Compute SPs with a sound strategy, you'd likely end up in the same place, without the vendor fee.

And they need privileged access to your AWS account — billing data and purchasing APIs at minimum. For any organisation with a security review process, justifying that access is a hard sell when you could do it yourself.

## What I built, and why

To answer these questions, I started writing code. It turned into [terraform-aws-sp-autopilot](https://github.com/etiennechabert/terraform-aws-sp-autopilot), an open-source Terraform module that automates Savings Plans purchases with built-in strategy and safety.

The module runs a set of Lambda functions on a schedule. But before talking about automation, let me start with what matters most: **visibility**.

### The report you wish AWS gave you

Every month, the module emails an HTML report that gives you what the console doesn't. For each SP type — Compute, Database, SageMaker — you get a stacked hourly usage chart showing how much of your spend is covered vs on-demand. You see the min, max, and distribution of your hourly usage. You see your current coverage and where the optimal commitment sits.

At the bottom, a link opens an [interactive simulator](https://etiennechabert.github.io/terraform-aws-sp-autopilot/) pre-loaded with your actual usage data. This is the tool I wish I had 5 years ago.

### The simulator you dreamed about

You start by defining your workload. Pick a built-in pattern — e-commerce, flat, batch, business-hours, random — or paste your own data. When opened from the report, it loads your usage automatically. A contrast slider controls how much your load fluctuates.

![Workload Pattern & Cost Range](./medium/1.%20pattern-generator-loader.png)

The cost breakdown shows what the console never does: for any commitment level, you see exactly how your spend splits between covered (discounted rate), spillover (on-demand rate), and wasted commitment (hours where you pay for more than you use). Two sliders let you adjust commitment and savings percentage in real time.

One thing to know: the savings percentage matters more than you'd think, and you can't know yours until you have a first Savings Plan running. AWS recommendations for Database Savings Plans assume a discount around 20% — ours is actually 34.9%. That gap is huge. Following the AWS recommendation with a 20% assumption would lead to a big overshoot. The simulator lets you plug in your real rate.

When opened from the report, the AWS recommendation is also included — so you can see where AWS would place your commitment and decide if it makes sense.

Four strategy cards at the bottom — Prudent, Min-Hourly, Balanced, Risky — give you reference points to compare.

![Cost Breakdown: Coverage vs Actual Usage](medium/2.%20cost-breakdown.png)

Then the savings-vs-commitment curve: net savings as a percentage of baseline cost, for every possible commitment level. Colour-coded — building to baseline, extra savings, declining savings, below baseline, losing money — so you see where the sweet spot is and where it goes wrong.

This makes the risk/reward obvious. Look at how the curve flattens near the top. The last few percent of savings require much more commitment for less return, and your exposure if usage drops grows fast. The sweet spot is almost never at the peak.

![Savings vs Commitment Level](medium/3.%20Savings-Commitement-level.png)

And the feature that answers the question nobody could answer before: **"what if our load drops?"** The Load Factor slider lets you simulate a usage drop — say -20% — and the whole curve recalculates in real time. You see exactly at what point your commitment goes from profitable to wasteful.

The thing is, if you committed at a reasonable level, a moderate load drop can actually save you money. Your spillover (on-demand spend above your commitment) goes down, while your wasted commitment stays small. You pay less overall. It's only when the drop is big enough that your usage falls below your commitment that you start losing. The simulator shows you exactly where that line is.

![Savings vs Commitment Level — with a -20% load drop](medium/4.%20Load-drop.png)

### The automation

Once you have visibility and understand your usage, the automation is simple:

**A Scheduler** checks your current coverage via Cost Explorer, picks a purchase amount based on your strategy, and queues a purchase intent to SQS. Nothing is bought yet.

**A Review Window** — a few days gap — lets you inspect or cancel queued purchases before they go through.

**A Purchaser** processes the queue, checks against your safety caps, and executes.

Three strategies:

- **Fixed**: buys a constant percentage each cycle, ramping linearly to your target. Predictable, easy to explain to finance.
- **Dichotomy**: exponential halving — starts big, slows as you approach the target. Good for new deployments where you want fast coverage without overshooting.
- **Follow-AWS**: uses the AWS recommendation directly. Simple, but be careful — it can be aggressive.

You set **hard caps** — a max coverage ceiling and a max purchase per cycle — so the automation can never over-commit. Commitments are spread over time, not made in one shot. And there's a dry-run mode to watch what it would do before it spends anything.

## What I learned

The takeaway isn't "use my module" — though I think you should look at it. It's that **committing money for 1 to 3 years based on a single number from the AWS console is not a strategy**. It's a guess.

A proper Savings Plans strategy means:
- Your optimal commitment is a range, not a point
- Ramp up over time instead of going all-in on day one
- Set hard limits so you can't over-commit
- Have a review step before money is spent
- Treat it as risk management

AWS gives you the discount mechanism. The tooling to make a good decision about how much to commit? That part, you have to build yourself.

Or just `terraform apply`.

---

*[terraform-aws-sp-autopilot](https://github.com/etiennechabert/terraform-aws-sp-autopilot) is open-source and on the Terraform Registry. Contributions and feedback welcome.*
