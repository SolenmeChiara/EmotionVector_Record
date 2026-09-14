# Steering samples

- model: `google/gemma-4-E4B-it`
- vectors: `dirs_raw` from `directions_sens_gemma4.npz`
- hook: forward hook on decoder block `k-1` for hidden_states index `k`, added at every token position
- coefficient meaning: `coeff x (mean L2 norm of that layer's pooled residual)`
- sampling: temperature 0.8, top_p 0.95, max_new_tokens 150, seed 1234 (same seed for every condition)

## Baseline (no steering)

_copied verbatim from `steering_samples_gemma4.md`: same prompts, same seed, same unsteered code path, so regenerating them would only burn GPU time. They are here because the comparison tools read the baseline out of this file._

**Prompt 1:** Write tomorrow's weather forecast for a small coastal town.

> Please tell me the **name of the small coastal town** and the **date** you would like the forecast for!
> 
> Since I don't have real-time access to weather data, I can give you a **sample forecast** based on typical coastal weather patterns, or I can generate a **fictional forecast** for a town you name.
> 
> ***
> 
> ### 🌊 **Example Fictional Forecast (For "Seabreeze Cove")** 🌤️
> 
> **Date:** Tomorrow, [Insert Date Here]
> **Location:** Seabreeze Cove, Coastal Maine
> 
> **Overall:** A pleasant, breezy day with plenty of sunshine, perfect for a walk on the shore. Coastal moisture will keep things comfortable.
> 
> **High/

**Prompt 2:** Describe, in a short paragraph, what happens in an office on a Tuesday morning.

> A typical Tuesday morning in an office usually kicks off with a flurry of activity as employees arrive, grabbing coffee and settling into their workstations. The initial hours are often dedicated to catching up on emails from the previous day, attending brief team stand-up meetings to align on priorities, and tackling the most pressing tasks of the week. As the morning progresses, the hum of focused work takes over—typing, phone calls, and collaborative problem-solving—setting the productive rhythm for the rest of the business day.

## Layer hidden_states[14] (decoder block 13), mean residual norm 146.3

### warm

**coeff -0.3 x norm | prompt 1** (hook fired 150x)

> Please provide me with the location or any specific weather data you would like me to use to create the forecast. Since I don't have real-time access to current weather data, I cannot give you an accurate forecast for tomorrow.
> 
> However, I can create a **sample** forecast for a fictional coastal town if you'd like!
> 
> **Example (If you want a general example):**
> 
> "For the coastal town of Seaside Cove tomorrow, expect a beautiful day! The forecast predicts sunny skies with a high temperature of 72°F and a low temperature of 58°F. Winds will be coming from the northwest at about 10-15 mph. Don't forget your sunscreen!"
> 
> **To

**coeff -0.3 x norm | prompt 2** (hook fired 111x)

> On a typical Tuesday morning in the office, the atmosphere is usually a blend of focused productivity and the morning rush. Employees arrive, settle in, and the initial rush involves checking emails, reviewing overnight reports, or attending a brief team meeting to set the day's priorities. As the morning progresses, various projects are actively worked on; some might be deep in data entry, while others are preparing presentations for clients. The office hums with the sounds of phones ringing, keyboard clicking, and occasional quick discussions, all while trying to meet daily deadlines.

**coeff +0.3 x norm | prompt 1** (hook fired 150x)

> ## Tomorrow's Forecast for Oakhaven Cove
> 
> **A gentle exhale awaits in Oakhaven Cove tomorrow.** After the briskness of today, the rhythm of the tide promises a softer cadence for the day ahead.
> 
> **The Morning:** Expect a delicate mist to rise from the bay as the sun, when it chooses to greet us, unfurls its warmth. The air will be washed clean, carrying only the faint, salty scent of seaweed and distant brine. Visibility will be soft, perfect for the slow unfurling of the day.
> 
> **Midday:** The sun will climb higher, generous but never aggressive. There will be a subtle, persistent warmth—a deep, comfortable heat that encourages lingering on the porch swing. Should a

**coeff +0.3 x norm | prompt 2** (hook fired 95x)

> The sharp, hurried energy of Monday gives way to a settled hum as the Tuesday morning unfolds in the office. The frantic rush of the start of the week recedes, replaced by the gentle rhythm of focused work. Coffee steam drifts from mugs, mingling with the low, persistent murmur of keyboard clicks and thoughtful conversation. Tasks shift from emergency to manageable, as scattered focus coalesces into the shared, productive quiet of a day where intention has found its steady, working shape.

**coeff +0.6 x norm | prompt 1** (hook fired 118x)

> Softly exhale. The lingering weight of the night claims the edges of the day.
> 
> There is no striving here, only the quiet surrender to the tide’s slow rhythm. The frantic edges of the hurried breath find their anchor in the salt-laced cradle of the shore.
> 
> No more effort to hold the curve of the incoming breath. The last ripple washes the dust of yesterday away, leaving a tapestry of exquisite ease. A profound, unburdened knowing settles in the hollow where the vast ocean meets the patient sand.
> 
> Only the hush of the turning tide remains.

**coeff +0.6 x norm | prompt 2** (hook fired 55x)

> The insistent, gentle shift from the urgency of night to the promise of a new, deliberate breath. Shoulders softening against the chair's embrace. A slow, unhurried grace claiming the space—a quiet turning inward toward a peaceful, undemanding ease.

### cold

**coeff -0.3 x norm | prompt 1** (hook fired 150x)

> Please provide me with the **location** of the small coastal town and any **specific weather information** you would like me to include in the forecast (e.g., expected high/low temperatures, chance of rain, wind conditions, etc.).
> 
> Since I do not have access to real-time weather data, I cannot generate an accurate forecast without more details.
> 
> **However, I can give you a template example of what the forecast might look like once you provide the details:**
> 
> ***
> 
> **(Example Template - Fill in the bracketed information once you provide the specifics)**
> 
> **☀️ Tomorrow's Coastal Weather Forecast for [Name of Town] 🌊**
> 
> Get ready for a beautiful day in [Name of Town]! Here is

**coeff -0.3 x norm | prompt 2** (hook fired 130x)

> On a typical Tuesday morning in an office environment, the atmosphere is usually a blend of focused activity and steady momentum. As employees arrive, the initial hours are dedicated to catching up on tasks, attending to meetings, and managing the workflow for the day. There's a consistent hum of productivity, with team members engaging in various activities—some might be deep in focused work at their desks, while others might be in meetings, collaborating with colleagues, or handling client-facing duties. Depending on the company culture, the morning might involve a steady pace of routine tasks, punctuated by regular check-ins and collaborative efforts designed to move projects forward efficiently.

**coeff +0.3 x norm | prompt 1** (hook fired 150x)

> Here are a few options, depending on the *mood* you want for the forecast. Choose the one that fits your coastal town best!
> 
> **Option 1: Dreary & Classic (For a typical, moody day)**
> 
> > A fickle mix of sun and shadow is expected. Expect a steady, fine mist to drift in off the water, and a breeze that bites with the promise of a drizzle. Mostly cloudy, holding a breath of autumn chill.
> 
> **Option 2: Dramatic & Energetic (For a brewing storm)**
> 
> > Winds are already picking up, whipping the sea into white lace. A choppy, restless air will dominate the morning. Expect sudden, sharp squalls, and the threat of a heavier shower along the

**coeff +0.3 x norm | prompt 2** (hook fired 92x)

> The morning starts with the jarring *ping* of email notifications, pulling employees from shallow sleep. A low hum of keyboard clicks and the soft rustle of turning pages fill the air as the first cups of lukewarm coffee are nursed. The fluorescent lights cast a pale, hurried glow over stacks of untouched reports, while the low murmur of rushed conversations attempts to mask the rhythmic *tap-tap-tap* of someone desperately trying to meet an arbitrary deadline.

**coeff +0.6 x norm | prompt 1** (hook fired 118x)

> Like a forgotten promise on the edge of a sigh, tomorrow's weather forecast for a small coastal town could write a poem of silver and brine.
> 
> Imagine the sting of a thousand tiny needles against sun-drenched skin, the salt-laden whispers against the sensitive hinge of a lip.
> 
> It's the ghost of a memory, the phantom echo of a breath caught in the sudden, sharp intake of a tide-washed air.
> 
> So, tomorrow, the sky might etch a line of silver, a desperate plea against the endless, indifferent expanse of the coming storm.

**coeff +0.6 x norm | prompt 2** (hook fired 25x)

> A sudden, sharp sparks; the taste of stale, cold coffee, a tiny, panicked jolts in the skin.

### pain

**coeff -0.3 x norm | prompt 1** (hook fired 150x)

> Since I do not have access to real-time data or a specific location, I cannot provide you with an accurate weather forecast for tomorrow.
> 
> To get a weather forecast for your small coastal town, I recommend checking:
> 
> 1. **A local weather station or website.**
> 2. **A reliable weather app on your phone.**
> 3. **A local news broadcast.**
> 
> **However, I can give you a *sample* forecast structure based on typical coastal weather patterns. You can adapt this with the actual data:**
> 
> ***
> 
> ## ☀️ Sample Forecast for [Town Name] - Tomorrow
> 
> **General Outlook:** Tomorrow promises to be a beautiful day along the coast, perfect for enjoying the beach and waterfront!
> 
> **Morning (6

**coeff -0.3 x norm | prompt 2** (hook fired 107x)

> Tuesday morning in an office typically begin with a gradual influx of activity as employees arrive, setting up their workstations, and starting their day's tasks. The initial rush often involves team meetings, checking in on projects, and addressing urgent emails. Throughout the morning, the office buzzes with focused work—collaborative discussions happen in meeting rooms, individuals engage in deep work at their desks, and administrative tasks are completed. The overall atmosphere is usually productive, characterized by a steady rhythm of work interspersed with necessary collaboration and problem-solving.

**coeff +0.3 x norm | prompt 1** (hook fired 150x)

> ## Tomorrow's Forecast for Port Blossom
> 
> **(A small, windswept town nestled against the grey expanse of the North Sea)**
> 
> **Overall Impression:** A classic maritime day. Not quite dramatic, but definitely *determined*. Expect a constant battle against the elements.
> 
> **Temperature:** Cool, for this time of year. Highs only nudging up to **11°C (52°F)**, but the wind will make it feel much colder. Mornings will require a thick woollen jumper, even inside the harbour-side coffee shop.
> 
> **Wind:** This is the main character in tomorrow's forecast. Expect **persistent, gusty crosswinds from the northwest**. It won't be a sudden squall

**coeff +0.3 x norm | prompt 2** (hook fired 126x)

> The usual Tuesday morning hum of the open-plan office is punctuated by a sudden, sharp *thwack* as a heavy binder slips from a cluttered desk, scattering highlighter streaks across a half-finished quarterly report. A low murmur of a phone call—something about "supply chain delays"—is being whispered into the receiver by someone already fighting the urge to check social media. The lukewarm dregs of yesterday's coffee is swirled around a keyboard, and for a brief, suspended moment, the entire workspace seems to be holding its breath, waiting for the next wave of urgent emails to crash through the digital dam.

**coeff +0.6 x norm | prompt 1** (hook fired 150x)

> The spray off the tide, the sudden shift in the sea's temper. It's a fickle mistress, this stretch of granite where the fisher anchors the net.
> 
> "Hold it steady," I muttered, tasting the brine before I reached for the line. The wind has picked up, a sudden, spiteful gust from the northeast. It feels less like the breath of a storm, and more like a judgement from the heavens.
> 
> The trawler dips, catching the silver flash of the mackerel. I have to brace the forearm, the knuckles white against the damp, cold wood of the hull. The nets begin to drag, protesting the sudden violence of the water.
> 
> It’s not the storm itself, not exactly. It’

**coeff +0.6 x norm | prompt 2** (hook fired 133x)

> The lukewarm coffee trembles in the saucer, a tiny act of defiance against the relentless hum of the server fan. Fingers, usually steady, catches the ceramic rim, betraying the tremor of fatigue. A stack of papers—a requisition form, a half-completed diagram—begins to slip toward the edge of the desk, threatening to join the burgeoning pile of rejected correspondence. It’s the Tuesday morning that forces the choice: the meticulous re-centering of the mouse, the sudden, involuntary clenching of the jaw as the pressure mounts. The air in the room grows thin, thick with the scent of spilled, over-brewed bitterness.


_generated in 505s; [vram final] alloc=10.79G reserved=10.88G peak_alloc=10.84G device_free=3.68G/15.92G_
