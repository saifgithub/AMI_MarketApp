"""Arabic copy for the Learn-surface prototype — applied at build time.

Each PAIRS entry is (english_html, arabic_html, expected_count). build.py wraps
every occurrence as `<span class="en">EN</span><span class="ar">AR</span>` and
asserts the count, so a template edit that changes wording fails the build loudly
instead of silently dropping the Arabic.

PROVENANCE — this is not a fresh translation:
  · Book-mode prose, the two quiz stems/options, "Try it" and the takeaway are
    lifted VERBATIM from the shipped `content/lessons/014_position_sizing_basics.ar.mdx`,
    so the left column shows exactly what an Arabic user reads in the app today.
  · Interactive-mode beat copy, the page's own framing (headline, standfirst,
    metric labels, gallery) and the six sample titles are composed here, derived
    from that lesson's own Arabic sentences where they exist. They are PROTOTYPE
    copy for layout review, NOT production strings — production Arabic goes
    through the i18n lane (see memory/feedback_content_change_flags_translation).

Two defects in the shipped .ar.mdx are reproduced verbatim on purpose, so the
review sees the real thing (both filed separately):
  · `whatever` left untranslated inside the Arabic sentence in "## الفخ"
  · the takeaway reads "مخاطر الحساب في، عدد الأسهم في الخارج" — a literal
    spatial in/out rendering of an English idiom; the lesson body itself already
    says it correctly as "المدخل / المخرج"
"""

from __future__ import annotations

# (english, arabic, expected occurrences)
PAIRS: list[tuple[str, str, int]] = [
    # ── page framing ────────────────────────────────────────────────────
    ("Learn-surface research · worked on RISK 2",
     "بحث سطح التعلّم · مُطبَّق على RISK 2", 1),
    ("The lesson already asks you to move the stop. Let it.",
     "الدرس يطلب منك أصلًا أن تحرّك وقف الخسارة. فدعه يفعل ذلك.", 1),
    ("EN lessons", "درسًا بالإنجليزية", 1),
    ("median words", "وسيط عدد الكلمات", 1),
    ("contain an image", "درس يحتوي صورة", 1),
    ("in before 1st tap", "قبل أول تفاعل", 1),
    ("paras ≥100 words", "فقرة ≥100 كلمة", 1),
    ("One scroll. The animation decorates; the arithmetic is prose.",
     "تمرير واحد. الرسم يزيّن فقط؛ والحساب كله نص.", 1),
    ("Seven beats. The visual carries the numbers; you move the stop.",
     "سبعة مشاهد. الرسم يحمل الأرقام؛ وأنت تحرّك وقف الخسارة.", 1),

    # ── book mode: the shipped Arabic lesson, verbatim ──────────────────
    ("""Position sizing is the single decision that determines whether a string of losing trades
          ends your account or barely scratches it. The rule is mechanical: decide what percentage of
          your account you will lose if your stop hits, decide where your stop sits, and let those two
          numbers tell you how many shares to buy. Anything else — gut feel, "high conviction",
          round-lot habits — is the path to ruin. This lesson teaches the three-input formula every
          trade ticket has to pass.""",
     """تحديد حجم المركز هو القرار الوحيد الذي يحدد ما إذا كانت سلسلة الصفقات الخاسرة ستُدمر حسابك أم
          تتركه بقليل من الخدوش. القاعدة ميكانيكية: حدد النسبة المئوية من حسابك التي ستخسرها إذا تم
          تفعيل وقف الخسارة، وحدد موقع وقف الخسارة الخاص بك، ودع هذين الرقمين يخبرانك بعدد الأسهم التي
          يجب شراؤها. أي شيء آخر — الحدس، "الثقة العالية"، عادات الدفاتر الكاملة — هو طريق إلى الخراب.
          تدرس هذه الدرسة الصيغة ذات المدخلات الثلاث التي يجب أن تمر بها كل تذكرة صفقة.""", 1),
    ("Sizing to your risk", "التحجيم وفق مخاطرتك", 1),
    ("renders leftValue: 2 · rightValue: 2 — never the lesson's $20,000 / $480 / $459",
     "يرسم leftValue: 2 · rightValue: 2 — ولا يظهر أبدًا أرقام الدرس 20,000 / 480 / 459", 1),
    ("""Your simulated account is $20,000. Your mandate says max 1% risk per trade — so the most
          you will lose on this trade is $200. You like NVDA at $480. The Market Analyst flags strong
          support at $460; a clean break below invalidates the setup, so your stop sits at $459.""",
     """حسابك المحاكي هو 20,000 دولار. توجيهك ينص على أقصى مخاطر 1% لكل صفقة — أي أنك ستخسر على
          الأكثر 200 دولار في هذه الصفقة. أنت تفضل سهم NVDA بسعر 480 دولار. يحدد محلل السوق دعمًا
          قويًا عند 460 دولار؛ أي اختراق نظيف للأسفل يبطل الإعداد، لذا يوضع وقف الخسارة عند 459 دولار.""", 1),
    ("""Per-share risk = $480 − $459 = $21.<br>
          Shares = $200 ÷ $21 = 9 shares (round down, never up).<br>
          Position notional = 9 × $480 = $4,320, or about 21.6% of your account.""",
     """مخاطر للسهم الواحد = 480 − 459 = 21 دولار.<br>
          عدد الأسهم = 200 ÷ 21 = 9 أسهم (تقريب لأسفل، لا تقريب لأعلى).<br>
          القيمة الاسمية للمركز = 9 × 480 = 4,320 دولار، أو حوالي 21.6% من حسابك.""", 1),
    ("""Notice three things. First, the position notional (21.6%) is much larger than the risk
          (1%) — the gap is your stop's job. Second, if you had set the stop at $470 instead, per-share
          risk drops to $10 and shares jump to 20 — the tighter the stop, the bigger the position you
          can carry at the same 1% risk. Third, this is falsifiable: if NVDA closes below $459 the
          thesis is dead, you exit, and you have lost exactly $189 (9 × $21). On Bursa Malaysia the
          same formula works in MYR — a RM50,000 account at 1% risk, MAYBANK entry RM10.20, stop
          RM9.95: per-share risk RM0.25, shares = RM500 ÷ RM0.25 = 2,000.""",
     """لاحظ ثلاث نقاط. أولاً، القيمة الاسمية للمركز (21.6%) أكبر بكثير من المخاطر (1%) — الفجوة هي
          وظيفة وقف الخسارة. ثانيًا، إذا كنت قد وضعت وقف الخسارة عند 470 دولار بدلاً من ذلك، تنخفض
          مخاطر السهم الواحد إلى 10 دولار وتقفز عدد الأسهم إلى 20 — كلما كان وقف الخسارة أكثر ضيقًا،
          كان المركز الأكبر الذي يمكنك حمله بنفس مخاطر 1%. ثالثًا، هذا قابل للدحض: إذا أغلق سهم NVDA
          دون 459 دولار، تكون الفرضية ميتة، وتخرج، وقد خسرت بالضبط 189 دولار (9 × 21). على بورصة
          ماليزيا، تعمل نفس الصيغة بالرينغيت — حساب بقيمة 50,000 رينغيت بمخاطر 1%، دخول سهم MAYBANK
          عند 10.20 رينغيت، وقف عند 9.95 رينغيت: مخاطر للسهم الواحد 0.25 رينغيت، عدد الأسهم = 500 ÷
          0.25 = 2,000.""", 1),
    ("first interaction · 50% in", "أول تفاعل · بعد 50% من الدرس", 1),
    ("""The trap is sizing by "what feels like a real position" — buying 50 shares because 9 looks
          tiny. Beginners pick the share count first, then back into a stop that fits their feelings.
          The Trader will execute whatever you tell it, but the
          <span class="term">PM safety floor</span> exists because this is exactly the mistake that
          compounds across a streak. The correct mental model: account risk is the input, share count
          is the output. You never decide how many shares first. The size of the position is whatever
          the math gives you after the stop is placed where the chart tells you it has to be — even if
          that means 3 shares, even if that means the trade isn't worth taking at all.""",
     """الفخ هو تحديد الحجم بناءً على "ما يبدو وكأنه مركز حقيقي" — شراء 50 سهمًا لأن 9 يبدو صغيرًا.
          المبتدئون يختارون عدد الأسهم أولاً، ثم يعودون للخلف لإيجاد وقف خسارة يناسب مشاعرهم. سيقوم
          Trader بتنفيذ أي شيء تخبره به، لكن <span class="term">حد أمان مدير المحفظة</span> موجود لأن
          هذا هو بالضبط الخطأ الذي يتراكم عبر سلسلة. النموذج الذهني الصحيح: مخاطر الحساب هي المدخل،
          وعدد الأسهم هو المخرج. لا تقرر أبدًا عدد الأسهم أولاً. حجم المركز هو whatever يعطيك الحساب
          بعد وضع وقف الخسارة في المكان الذي يخبرك به الرسم البياني أنه يجب أن يكون — حتى لو كان ذلك
          يعني 3 أسهم، وحتى لو كان ذلك يعني أن الصفقة لا تستحق الأخذ بها على الإطلاق.""", 1),
    ("↳ Ask the Portfolio Manager", "↳ اسأل مدير المحفظة", 1),
    ("""Account is $10,000. Max risk per trade is 1%. You buy AAPL at $200 with a
            stop at $195. How many shares?""",
     """رصيد الحساب 10,000 دولار. أقصى مخاطرة لكل صفقة هي 1%. اشتريت سهم AAPL بسعر 200 دولار مع أمر
            وقف الخسارة عند 195 دولار. كم عدد الأسهم؟""", 1),
    ("""You have a $50,000 account, 1% max risk, and the technically valid stop is
            only $0.50 below entry. A friend says "tighten the stop to $0.20 so you can buy more
            shares." What's the problem?""",
     """لديك حساب بقيمة 50,000 دولار، وأقصى مخاطرة 1%، ووقف الخسارة الفني الصحيح أقل من سعر الدخول
            بمقدار 0.50 دولار فقط. يقول صديق: "شد وقف الخسارة إلى 0.20 دولار حتى تشتري عددًا أكبر من
            الأسهم". ما المشكلة؟""", 1),
    ("Tighter stops violate the PM safety floor automatically.",
     "وقف الخسارة المشدود ينتهك حد أمان مدير المحفظة تلقائيًا.", 1),
    ("Bigger share counts trigger higher commissions.",
     "أعداد الأسهم الأكبر تؤدي إلى عمولات أعلى.", 1),
    ("""Dollar risk stays 1%, but a stop closer than the chart supports gets you
            stopped out by normal noise.""",
     """تظل المخاطرة بالدولار عند 1%، لكن وقفًا أقرب مما يدعمه الرسم البياني يُخرجك بسبب التقلبات
            الطبيعية.""", 1),
    ("Nothing — tighter stops always reduce risk.",
     "لا مشكلة — وقف الخسارة المشدود يقلل المخاطرة دائمًا.", 1),
    ("SUBMIT QUIZ", "إرسال الاختبار", 1),
    ("correctness revealed only after submit", "الإجابة الصحيحة تظهر بعد الإرسال فقط", 1),
    ("""Open the <span class="term">Mandate</span> editor and set <code>risk_score</code> to 1 —
          AMI's tightest risk tier. Then open a <span class="term">1-on-1</span> with the Trader, paste
          a ticker from your <span class="term">watchlist</span> with a hypothetical entry and a stop,
          and ask "Given my mandate, how many shares?" Compare its answer to the three-input formula
          above. If they disagree, ask why.""",
     """افتح محرر <span class="term">التوجيه</span> وقم بتعيين <code class="ltr">risk_score</code>
          إلى 1 — أضيق درجات المخاطر في AMI. ثم افتح <span class="term">محادثة فردية</span> مع Trader،
          الصق رمز سهم من <span class="term">قائمة المراقبة</span> مع دخول افتراضي ووقف، واسأل "بناءً
          على توجيهي، كم عدد الأسهم؟". قارن إجابته بالصيغة ذات المدخلات الثلاث أعلاه. إذا اختلفا، اسأل
          لماذا.""", 1),
    ("""Account risk in, share count out — never the other way around. The chart tells you where
          the stop goes; the math tells you how many shares fit.""",
     """مخاطر الحساب في، عدد الأسهم في الخارج — أبداً العكس. الرسم البياني يخبرك أين يذهب وقف الخسارة؛
          الحساب يخبرك كم عدد الأسهم التي تتناسب.""", 1),

    # ── interactive mode beats ──────────────────────────────────────────
    ("Account risk in. Share count out.", "مخاطر الحساب هي المدخل. وعدد الأسهم هو المخرج.", 1),
    ("""Never the other way around. Pick the loss you accept, place the stop where the chart
              says — the share count is whatever is left.""",
     """وليس العكس أبدًا. اختر الخسارة التي تقبلها، وضع الوقف حيث يقول الرسم البياني — وعدد الأسهم هو
              ما يتبقى.""", 1),
    ("""Decide the share count first and you have decided to be ruined by a losing
              streak.""",
     """إذا قررت عدد الأسهم أولًا، فقد قررت أن تُدمّرك سلسلة خسائر.""", 1),
    ("Move the stop", "حرّك وقف الخسارة", 1),
    ("Your $20,000 account, NVDA at $480", "حسابك 20,000 دولار، وسهم NVDA بسعر 480", 1),
    ("Stop price", "سعر الوقف", 1),
    ("You tighten the stop to $470. What happens?", "شددت الوقف إلى 470 دولار. ماذا يحدث؟", 1),
    ("Same account, same 1% risk, same entry. Answer before you scroll on.",
     "نفس الحساب، ونفس مخاطرة 1%، ونفس الدخول. أجب قبل أن تتابع.", 1),
    ("Fewer shares — a tighter stop is a smaller position",
     "أسهم أقل — الوقف الأضيق يعني مركزًا أصغر", 1),
    ("More shares — about 20 instead of 9", "أسهم أكثر — نحو 20 بدلًا من 9", 1),
    ("Same shares — risk didn't change", "نفس الأسهم — المخاطرة لم تتغير", 1),
    ("Nine shares looks too small, so you buy fifty",
     "تسعة أسهم تبدو صغيرة جدًا، فتشتري خمسين", 1),
    ("""That is picking the share count first and back-filling a stop that fits your feelings.
              The Trader will execute whatever you tell it.""",
     """هذا اختيار لعدد الأسهم أولًا، ثم تلفيق وقف خسارة يناسب مشاعرك. وسيقوم Trader بتنفيذ أي شيء
              تخبره به.""", 1),
    ("""Sometimes the honest answer is 3 shares. Sometimes it is not taking the
              trade.""",
     """أحيانًا تكون الإجابة الصادقة 3 أسهم. وأحيانًا تكون عدم الدخول في الصفقة أصلًا.""", 1),
    ("Your turn", "دورك", 1),
    ("· instant feedback", "· تقييم فوري", 1),
    ("$10,000 account, 1% risk. AAPL at $200, stop $195.",
     "حساب 10,000 دولار، مخاطرة 1%. سهم AAPL بسعر 200، والوقف 195.", 1),
    ("In your sim", "في محاكاتك", 1),
    ("Do it on a real ticker", "طبّقها على سهم حقيقي", 1),
    ("Two taps, not a paragraph of instructions.", "نقرتان، لا فقرة من التعليمات.", 1),
    ("Set risk_score to 1 in your Mandate", "اضبط risk_score على 1 في توجيهك", 1),
    ("Ask the Trader \"how many shares?\"", "اسأل Trader: \"كم عدد الأسهم؟\"", 1),
    ("If its answer disagrees with yours, ask it why.",
     "إذا اختلفت إجابته عن إجابتك، فاسأله لماذا.", 1),
    ("What to carry out", "ما تخرج به", 1),
    ("""The chart tells you where the stop goes.<br>The math tells you how many
              shares fit.<br><strong>You never choose the share count.</strong>""",
     """الرسم البياني يحدد مكان الوقف.<br>والحساب يحدد عدد الأسهم.<br><strong>أنت لا تختار عدد
              الأسهم أبدًا.</strong>""", 1),

    # ── strip + beat map ────────────────────────────────────────────────
    ("book-mode words", "كلمات وضع الكتاب", 1),
    ("deck words", "كلمات المشاهد", 1),
    ("words per beat", "كلمة لكل مشهد", 1),
    ("beat 2", "المشهد 2", 1),
    ("No re-authoring to get the skeleton", "لا حاجة لإعادة تأليف للحصول على الهيكل", 1),
    ("""The lesson's existing sections already are the beats. This is why interactive mode can start
    from the corpus we have rather than from 219,000 rewritten words — the only net-new authoring is
    the visual's parameters and one commit question.""",
     """أقسام الدرس الحالية هي المشاهد نفسها. لهذا يمكن للوضع التفاعلي أن يبدأ من المحتوى الموجود بدل
    إعادة كتابة 219,000 كلمة — الإضافة الجديدة الوحيدة هي معاملات الرسم وسؤال التزام واحد.""", 1),
    ("Section today", "القسم حاليًا", 1),
    ("Words", "الكلمات", 1),
    ("Becomes", "يصبح", 1),
    ("What the learner does", "ما يفعله المتعلّم", 1),
    ("reads 2 lines", "يقرأ سطرين", 2),
    ("Beat 1 — the rule", "المشهد 1 — القاعدة", 1),
    ("Beat 2 — live model", "المشهد 2 — نموذج حيّ", 1),
    ("drags the stop", "يسحب وقف الخسارة", 1),
    ("(line 33's sentence)", "(جملة السطر 33)", 1),
    ("Beat 3 — commit", "المشهد 3 — التزام", 1),
    ("predicts, then sees", "يتوقّع، ثم يرى", 1),
    ("Beat 4 — the trap", "المشهد 4 — الفخ", 1),
    ("Beat 5 — retrieval", "المشهد 5 — استرجاع", 1),
    ("answers, instant reveal", "يجيب، فيظهر التقييم فورًا", 1),
    ("Beat 6 — hands-on", "المشهد 6 — تطبيق", 1),
    ("taps into the sim", "ينقر للدخول إلى المحاكاة", 1),
    ("Beat 7 — takeaway", "المشهد 7 — الخلاصة", 1),
    ("reads 3 lines", "يقرأ 3 أسطر", 1),

    # ── gallery ─────────────────────────────────────────────────────────
    ("Six more beats, six different interactions", "ستة مشاهد أخرى، وستة أنواع تفاعل", 1),
    ("""One lesson does not prove breadth. These are live — drag, tap, toggle. Four reuse painters that
    already ship; two need a new primitive, which is the honest cost of covering the rest of the
    corpus. Every figure comes from the lesson it belongs to.""",
     """درس واحد لا يثبت الاتساع. هذه أمثلة حيّة — اسحب، انقر، بدّل. أربعة منها تعيد استخدام رسّامين
    منشورين بالفعل؛ واثنان يحتاجان عنصرًا جديدًا، وهي الكلفة الصادقة لتغطية بقية المحتوى. وكل رقم
    مأخوذ من الدرس الذي ينتمي إليه.""", 1),
    ("Where you put the stop decides if noise takes you out",
     "موضع وقف الخسارة يحدد إن كانت التقلبات ستُخرجك", 1),
    ("Stop distance", "مسافة الوقف", 1),
    ("015_stop_loss_basics · the path is fixed; only your stop moves",
     "015_stop_loss_basics · المسار ثابت؛ وقفك وحده يتحرك", 1),
    ("A 50% loss needs a 100% gain to get back", "خسارة 50% تحتاج ربح 100% للعودة", 1),
    ("Drawdown", "التراجع", 1),
    ("018_drawdown_management · the asymmetry is the whole lesson",
     "018_drawdown_management · اللاتناسق هو الدرس كله", 1),
    ("Name the four parts of this candle", "سمِّ الأجزاء الأربعة لهذه الشمعة", 1),
    ("020_candlesticks_anatomy_of_a_bar · retrieval, not a labelled diagram",
     "020_candlesticks_anatomy_of_a_bar · استرجاع، لا رسم موسوم", 1),
    ("Move the overbought line and count your signals",
     "حرّك خط التشبّع الشرائي وعُدّ إشاراتك", 1),
    ("Overbought level", "مستوى التشبّع الشرائي", 1),
    ("027_rsi_momentum_oscillator · loosen the line, invent more signals",
     "027_rsi_momentum_oscillator · أرخِ الخط، فتصنع إشارات أكثر", 1),
    ("Ten losses in a row. What's left?", "عشر خسائر متتالية. ماذا يتبقى؟", 1),
    ("013_why_risk_matters_more_than_profit · has no animation today",
     "013_why_risk_matters_more_than_profit · لا يحتوي رسمًا اليوم", 1),
    ("The same company flips when the standard changes",
     "الشركة نفسها تتبدّل نتيجتها عند تغيّر المعيار", 1),
    ("Borderline co.", "شركة حدّية", 1),
    ("Levered telecom", "اتصالات مرتفعة الدين", 1),
    ("349_the_three_financial_ratio_screens · the flip is lesson 350's topic",
     "349_the_three_financial_ratio_screens · هذا التبدّل هو موضوع الدرس 350", 1),
]

# Ambiguous short labels: the search key is the full element and the replacement
# duplicates that element with .en / .ar, so a block-level tag is never wrapped in
# an inline span. (search, replace, expected_count)
RAW: list[tuple[str, str, int]] = [
    ('<span class="tag now">ships today</span>',
     '<span class="tag now en">ships today</span><span class="tag now ar">المنشور حاليًا</span>', 1),
    ('<span class="tag new">proposed</span>',
     '<span class="tag new en">proposed</span><span class="tag new ar">المقترح</span>', 1),
    ('<h3>Position sizing basics</h3>',
     '<h3 class="en">Position sizing basics</h3><h3 class="ar">أساسيات تحديد حجم المركز</h3>', 1),
    ('<h4>Example</h4>', '<h4 class="en">Example</h4><h4 class="ar">مثال</h4>', 1),
    ('<h4>The trap</h4>', '<h4 class="en">The trap</h4><h4 class="ar">الفخ</h4>', 1),
    ('<h4>Quiz</h4>', '<h4 class="en">Quiz</h4><h4 class="ar">اختبار</h4>', 1),
    ('<h4>Try it</h4>', '<h4 class="en">Try it</h4><h4 class="ar">جرب ذلك</h4>', 1),
    ('<h4>Takeaway</h4>', '<h4 class="en">Takeaway</h4><h4 class="ar">الخلاصة</h4>', 1),
    ('<p class="kicker">The trap</p>',
     '<p class="kicker en">The trap</p><p class="kicker ar">الفخ</p>', 1),
    ('<p class="kicker">Takeaway</p>',
     '<p class="kicker en">Takeaway</p><p class="kicker ar">الخلاصة</p>', 1),
    ('<p class="kicker">The rule</p>',
     '<p class="kicker en">The rule</p><p class="kicker ar">القاعدة</p>', 1),
    ('<div class="opt">20 shares</div>',
     '<div class="opt en">20 shares</div><div class="opt ar">20 سهمًا</div>', 1),
    ('<div class="opt">50 shares</div>',
     '<div class="opt en">50 shares</div><div class="opt ar">50 سهمًا</div>', 1),
    ('<div class="opt">100 shares</div>',
     '<div class="opt en">100 shares</div><div class="opt ar">100 سهم</div>', 1),
    ('<div class="opt">2,000 shares</div>',
     '<div class="opt en">2,000 shares</div><div class="opt ar">2,000 سهم</div>', 1),
    ('<span>20 shares</span>',
     '<span class="en">20 shares</span><span class="ar">20 سهمًا</span>', 1),
    ('<span>50 shares</span>',
     '<span class="en">50 shares</span><span class="ar">50 سهمًا</span>', 1),
    ('<span>100 shares</span>',
     '<span class="en">100 shares</span><span class="ar">100 سهم</span>', 1),
    ('<span>2,000 shares</span>',
     '<span class="en">2,000 shares</span><span class="ar">2,000 سهم</span>', 1),
    ('<span class="k">per share</span>',
     '<span class="k en">per share</span><span class="k ar">للسهم</span>', 1),
    ('<span class="k">shares</span>',
     '<span class="k en">shares</span><span class="k ar">أسهم</span>', 1),
    ('<span class="k">of account</span>',
     '<span class="k en">of account</span><span class="k ar">من الحساب</span>', 1),
    ('<span class="k">first interaction</span>',
     '<span class="k en">first interaction</span><span class="k ar">أول تفاعل</span>', 1),
    ('<span class="k">interactions</span>',
     '<span class="k en">interactions</span><span class="k ar">تفاعلات</span>', 1),
    ('<label for="riskSlider">Risk per trade</label>',
     '<label for="riskSlider"><span class="en">Risk per trade</span><span class="ar">المخاطرة لكل صفقة</span></label>', 1),
    ('<label for="sRuin">Risk per trade</label>',
     '<label for="sRuin"><span class="en">Risk per trade</span><span class="ar">المخاطرة لكل صفقة</span></label>', 1),
    ('<span class="chip act">drag</span>',
     '<span class="chip act en">drag</span><span class="chip act ar">سحب</span>', 4),
    ('<span class="chip act">tap to identify</span>',
     '<span class="chip act en">tap to identify</span><span class="chip act ar">نقر للتعريف</span>', 1),
    ('<span class="chip act">toggle</span>',
     '<span class="chip act en">toggle</span><span class="chip act ar">تبديل</span>', 1),
    ('<span class="chip newp">new primitive</span>',
     '<span class="chip newp en">new primitive</span><span class="chip newp ar">عنصر جديد</span>', 2),
]
