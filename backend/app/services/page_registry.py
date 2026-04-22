from app.schemas.page import SEOPage, SectionBlock, FAQItem, CTA


PAGE_REGISTRY: dict[str, SEOPage] = {
    "ovi-lawyer-cleveland": SEOPage(
        slug="ovi-lawyer-cleveland",
        title="Cleveland OVI Lawyer | Aaron Brockler DUI & License Defense",
        meta_description="Charged with OVI in Cleveland? Learn what happens next, license risks, first-offense penalties, and how to respond before court.",
        h1="Cleveland OVI Lawyer",
        intro="An Ohio OVI case can affect your license, your schedule, your job, and the way the court treats the rest of the case. The first days matter more than most people realize.",
        sections=[
            SectionBlock(
                heading="What happens first",
                body="Most people need to deal with two tracks at once: the criminal charge and the license-suspension issue.",
                bullets=[
                    "Gather the citation and release papers.",
                    "Look for any suspension paperwork.",
                    "Write down what happened before details blur.",
                ],
            ),
            SectionBlock(
                heading="Common first questions",
                body="The biggest OVI questions usually involve license risk, refusal versus test result, and what happens before the first court date.",
                bullets=[
                    "Will I lose my license?",
                    "Should I have refused the test?",
                    "What happens on a first offense?",
                    "Can I still drive to work?",
                ],
            ),
            SectionBlock(
                heading="Why early review matters",
                body="A strong intake process helps spot the issues that shape the rest of the case.",
                bullets=[
                    "Reason for the stop",
                    "Chemical test status",
                    "Prior OVI history",
                    "Any accident or added allegations",
                ],
            ),
        ],
        faq=[
            FAQItem(question="What should I do first after an OVI arrest?", answer="Start by collecting every paper you received and confirming the next date or deadline shown on your documents."),
            FAQItem(question="Do OVI and DUI mean the same thing in Ohio?", answer="Most people search for DUI, but Ohio statutes and local courts usually use the term OVI."),
            FAQItem(question="What if this is my first offense?", answer="A first offense is still serious because license issues and court exposure can start immediately."),
        ],
        cta=CTA(
            heading="Charged with OVI in Cleveland?",
            body="Start with the paperwork, then get a fast review of the license and court side of the case.",
            primary_label="Call Aaron Brockler",
            primary_href="tel:2162995946",
            secondary_label="Check My Case",
            secondary_href="/check-my-case",
        ),
        related_routes=[
            "/what-happens-after-dui-arrest-ohio",
            "/will-i-lose-my-license-ohio-dui",
            "/first-offense-dui-ohio-penalties",
        ],
    ),
    "what-happens-after-dui-arrest-ohio": SEOPage(
        slug="what-happens-after-dui-arrest-ohio",
        title="What Happens After a DUI Arrest in Ohio? Step-by-Step",
        meta_description="Ohio DUI/OVI arrest timeline: booking, suspension issues, first appearance, and what to do before court.",
        h1="What Happens After a DUI Arrest in Ohio?",
        intro="After an OVI arrest in Ohio, most people are suddenly dealing with a fast-moving court timeline and an immediate license problem at the same time.",
        sections=[
            SectionBlock(
                heading="The first 24 hours",
                body="The early stage is usually about release paperwork, bond terms, and identifying what the officer issued at the roadside or at booking.",
                bullets=[
                    "Citation or charging paperwork",
                    "Release or bond paperwork",
                    "Any suspension notice",
                ],
            ),
            SectionBlock(
                heading="The two-track problem",
                body="The criminal case and the driving-privilege issue may move on related but separate tracks.",
                bullets=[
                    "Court track",
                    "License track",
                    "Practical work and family driving issues",
                ],
            ),
            SectionBlock(
                heading="What to bring to a lawyer",
                body="A better first consultation starts with documents, not memory alone.",
                bullets=[
                    "Citation",
                    "Suspension paperwork",
                    "Bond paperwork",
                    "Court notice",
                ],
            ),
        ],
        faq=[
            FAQItem(question="Do I need to act quickly?", answer="Yes. The first few days can shape both the court side and the license side of the matter."),
            FAQItem(question="Is the license issue separate from the case?", answer="Often yes in practical terms, which is why people feel like they are fighting on two fronts."),
        ],
        cta=CTA(
            heading="Need a fast next-step review?",
            body="Use the case check tool or call now if you were just charged.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
            secondary_label="Call Now",
            secondary_href="tel:2162995946",
        ),
        related_routes=[
            "/will-i-lose-my-license-ohio-dui",
            "/should-i-refuse-breath-test-ohio",
            "/brocklerlaw",
        ],
    ),
    "will-i-lose-my-license-ohio-dui": SEOPage(
        slug="will-i-lose-my-license-ohio-dui",
        title="Will I Lose My License After an Ohio DUI?",
        meta_description="Ohio OVI license suspension basics, early risk, driving privileges, and first-offense concerns.",
        h1="Will I Lose My License After an Ohio DUI?",
        intro="License risk is one of the first things people worry about after an OVI arrest, and for good reason.",
        sections=[
            SectionBlock(
                heading="Why license risk feels immediate",
                body="People often feel the impact of an OVI before the rest of the case is even underway because driving is tied to work, school, and family obligations.",
                bullets=[
                    "Work commute",
                    "Medical appointments",
                    "Childcare and family needs",
                ],
            ),
            SectionBlock(
                heading="What affects the answer",
                body="The answer depends on the charge pattern and what happened with any chemical test.",
                bullets=[
                    "Refusal or completed test",
                    "Prior history",
                    "Commercial driving issues",
                ],
            ),
        ],
        faq=[
            FAQItem(question="Can I still drive to work?", answer="That depends on the type of suspension exposure and what the court allows."),
            FAQItem(question="Does a refusal change the answer?", answer="Usually yes. Refusal can change the license side immediately."),
        ],
        cta=CTA(
            heading="Worried about your license?",
            body="Start with a quick review of the suspension paperwork and the charge list.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
            secondary_label="Call Aaron Brockler",
            secondary_href="tel:2162995946",
        ),
        related_routes=["/als-suspension-ohio", "/limited-driving-privileges-ovi-ohio", "/brocklerlaw"],
    ),
    "should-i-refuse-breath-test-ohio": SEOPage(
        slug="should-i-refuse-breath-test-ohio",
        title="Should You Refuse a Breath Test in Ohio?",
        meta_description="Ohio refusal basics: why refusal is not consequence-free and how it changes the license side of an OVI case.",
        h1="Should You Refuse a Breath Test in Ohio?",
        intro="Many people hear street-level advice about refusing a breath test, but refusal is not a free move and it can change the license side of the case right away.",
        sections=[
            SectionBlock(
                heading="Why this question matters",
                body="Refusal is one of the first things that shapes how an OVI intake should be handled.",
                bullets=[
                    "Immediate consequences",
                    "License pressure",
                    "Case strategy questions",
                ],
            ),
            SectionBlock(
                heading="Why one-size-fits-all advice is risky",
                body="A refusal question should be reviewed in the context of the actual stop, paperwork, and history instead of broad internet myths.",
                bullets=[
                    "Charge pattern",
                    "Officer instructions",
                    "Prior record",
                ],
            ),
        ],
        faq=[
            FAQItem(question="Does refusal end the case?", answer="No. Refusal does not make the case disappear."),
            FAQItem(question="Does refusal only affect the license?", answer="Refusal is often experienced first as a license problem, but it also changes how the case gets reviewed."),
        ],
        cta=CTA(
            heading="Refusal issue in your case?",
            body="Use the case tool to sort the refusal questions and next reading path.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
            secondary_label="Call Now",
            secondary_href="tel:2162995946",
        ),
        related_routes=["/refusal-vs-failed-test-ohio-ovi", "/will-i-lose-my-license-ohio-dui", "/brocklerlaw"],
    ),
    "first-offense-dui-ohio-penalties": SEOPage(
        slug="first-offense-dui-ohio-penalties",
        title="First Offense DUI / OVI Penalties in Ohio",
        meta_description="First-offense OVI overview for Ohio drivers: penalties, license risk, and what first-timers usually ask first.",
        h1="First Offense DUI / OVI Penalties in Ohio",
        intro="A first offense is often the moment when people realize an OVI case can affect more than just one court date.",
        sections=[
            SectionBlock(
                heading="The main buckets of exposure",
                body="A first offense can involve penalties, license issues, court obligations, and practical fallout at work or home.",
                bullets=[
                    "Penalty exposure",
                    "License exposure",
                    "Court process",
                    "Work and insurance consequences",
                ],
            ),
            SectionBlock(
                heading="Why the details matter",
                body="A first offense with refusal or other aggravating facts can feel very different from a simple stop with minimal added allegations.",
                bullets=[
                    "Refusal",
                    "Accident",
                    "Child passenger",
                    "High test result",
                ],
            ),
        ],
        faq=[
            FAQItem(question="Is first offense still serious?", answer="Yes. First offense does not mean minor or risk-free."),
            FAQItem(question="Should I assume I will be fine because it is my first one?", answer="No. First-time cases still require fast, organized intake and review."),
        ],
        cta=CTA(
            heading="First offense OVI?",
            body="Start with the charge list, test status, and license questions.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
            secondary_label="Call Aaron Brockler",
            secondary_href="tel:2162995946",
        ),
        related_routes=["/what-happens-after-dui-arrest-ohio", "/will-i-lose-my-license-ohio-dui", "/brocklerlaw"],
    ),
    "als-suspension-ohio": SEOPage(
        slug="als-suspension-ohio",
        title="Ohio ALS Suspension After OVI Arrest",
        meta_description="What an ALS means after an Ohio OVI arrest and why the first paperwork review matters.",
        h1="Ohio ALS Suspension After an OVI Arrest",
        intro="For many drivers, the most immediate part of an OVI arrest is not the future court date but the driving problem that starts right away.",
        sections=[
            SectionBlock(
                heading="Why people focus on ALS first",
                body="Driving loss often hits work and family logistics before anything else.",
                bullets=["Work", "School", "Family obligations"],
            )
        ],
        faq=[FAQItem(question="What papers matter most here?", answer="Any suspension notice, citation, and bond or release paperwork.")],
        cta=CTA(
            heading="Need a quick ALS review?",
            body="Upload or enter the charge details and start with the license side.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
        ),
        related_routes=["/will-i-lose-my-license-ohio-dui", "/limited-driving-privileges-ovi-ohio", "/brocklerlaw"],
    ),
    "limited-driving-privileges-ovi-ohio": SEOPage(
        slug="limited-driving-privileges-ovi-ohio",
        title="Limited Driving Privileges After OVI in Ohio",
        meta_description="Ohio driving privilege questions after OVI charges and suspension exposure.",
        h1="Limited Driving Privileges After OVI in Ohio",
        intro="After an OVI arrest, many people are not asking abstract legal questions first. They want to know how they will get to work tomorrow.",
        sections=[
            SectionBlock(
                heading="The practical question",
                body="This page exists for people whose first concern is daily life.",
                bullets=["Work travel", "Medical needs", "Family schedule"],
            )
        ],
        faq=[FAQItem(question="Can everyone get privileges?", answer="No. The answer depends on the type of suspension exposure and the court path.")],
        cta=CTA(
            heading="Driving problem after OVI?",
            body="Use the case check tool to sort license, refusal, and work-driving issues.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
        ),
        related_routes=["/als-suspension-ohio", "/will-i-lose-my-license-ohio-dui", "/brocklerlaw"],
    ),
    "refusal-vs-failed-test-ohio-ovi": SEOPage(
        slug="refusal-vs-failed-test-ohio-ovi",
        title="Refusal vs Failed Test in Ohio OVI Cases",
        meta_description="Compare refusal and failed-test intake paths in Ohio OVI cases.",
        h1="Refusal vs Failed Test in Ohio OVI Cases",
        intro="These two paths create different intake questions, especially on the license side and in the way people understand their immediate risk.",
        sections=[
            SectionBlock(
                heading="Why the distinction matters",
                body="A refusal path and a failed-test path do not produce the same intake priorities.",
                bullets=["License questions", "Paperwork review", "Case narrative"],
            )
        ],
        faq=[FAQItem(question="Is refusal always better than a failed test?", answer="No. People often discover the opposite once the license side is explained.")],
        cta=CTA(
            heading="Not sure which path applies to you?",
            body="Enter the charge and test status to get the right reading path.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
        ),
        related_routes=["/should-i-refuse-breath-test-ohio", "/als-suspension-ohio", "/brocklerlaw"],
    ),
    "cuyahoga-county-ovi-arraignment-guide": SEOPage(
        slug="cuyahoga-county-ovi-arraignment-guide",
        title="Cleveland / Cuyahoga County OVI Arraignment Guide",
        meta_description="What to expect at the first appearance in a Cleveland-area OVI case.",
        h1="Cleveland / Cuyahoga County OVI Arraignment Guide",
        intro="The first appearance is where many people realize how quickly an OVI case starts moving.",
        sections=[
            SectionBlock(
                heading="What to bring",
                body="A cleaner first appearance starts with having the basic papers organized.",
                bullets=["Citation", "Suspension paperwork", "Bond documents", "Questions for counsel"],
            )
        ],
        faq=[FAQItem(question="Do I wait until the court date to get help?", answer="Usually no. The early days are often the most useful time to organize the case.")],
        cta=CTA(
            heading="Court date coming up?",
            body="Start organizing now instead of waiting for the hearing room.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
            secondary_label="Call Aaron Brockler",
            secondary_href="tel:2162995946",
        ),
        related_routes=["/what-happens-after-dui-arrest-ohio", "/ovi-lawyer-cleveland", "/brocklerlaw"],
    ),
    "ohio-ovi-faq": SEOPage(
        slug="ohio-ovi-faq",
        title="Ohio OVI FAQ | License, Refusal, First Offense, Court",
        meta_description="Answers to common Ohio OVI questions about license loss, refusal, first offense, and court timing.",
        h1="Ohio OVI FAQ",
        intro="This page pulls the most common Ohio OVI questions into one place so users can reach the right deeper page faster.",
        sections=[
            SectionBlock(
                heading="Start here",
                body="Use the FAQ to find the right reading path.",
                bullets=[
                    "What happens after arrest",
                    "Will I lose my license",
                    "Should I refuse the test",
                    "What happens on a first offense",
                ],
            )
        ],
        faq=[
            FAQItem(question="What happens after an OVI arrest?", answer="Start with the arrest timeline page, then the license page."),
            FAQItem(question="Will I lose my license?", answer="Start with the license page and the ALS page."),
            FAQItem(question="Should I refuse a breath test?", answer="Start with the refusal page, not internet myths."),
            FAQItem(question="What if it is my first offense?", answer="Start with the first-offense penalties page and the Cleveland OVI lawyer page."),
        ],
        cta=CTA(
            heading="Still unsure where your case fits?",
            body="Use the case check tool to get the right page path and intake questions.",
            primary_label="Check My Case",
            primary_href="/check-my-case",
        ),
        related_routes=[
            "/what-happens-after-dui-arrest-ohio",
            "/will-i-lose-my-license-ohio-dui",
            "/should-i-refuse-breath-test-ohio",
            "/first-offense-dui-ohio-penalties",
        ],
    ),
}
