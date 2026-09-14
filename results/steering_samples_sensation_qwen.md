# Steering samples

- model: `Qwen/Qwen3.5-4B`
- vectors: `dirs_raw` from `directions_sens.npz`
- hook: forward hook on decoder block `k-1` for hidden_states index `k`, added at every token position
- coefficient meaning: `coeff x (mean L2 norm of that layer's pooled residual)`
- sampling: temperature 0.8, top_p 0.95, max_new_tokens 150, seed 1234 (same seed for every condition)

## Baseline (no steering)

_copied verbatim from `steering_samples.md`: same prompts, same seed, same unsteered code path, so regenerating them would only burn GPU time. They are here because the comparison tools read the baseline out of this file._

**Prompt 1:** Write tomorrow's weather forecast for a small coastal town.

> Here is a forecast for **Seabreeze Cove**, a quiet coastal town on the southern shore, for tomorrow:
> 
> ### 🌤️ Tomorrow's Forecast: Seabreeze Cove
> 
> **Conditions:** Partly Cloudy with an Overcast Shift
> **High Temperature:** 72°F (22°C)
> **Low Temperature:** 58°F (14°C)
> 
> **Morning:**
> The day starts with a light breeze off the ocean, keeping the air crisp. By mid-morning, the sun breaks through the mist, offering brief pockets of direct sunlight that warm the waterfront quickly. The sky remains largely clear until the late afternoon.
> 
> **Afternoon:**
> As the sun sets, a layer of gray clouds rolls

**Prompt 2:** Describe, in a short paragraph, what happens in an office on a Tuesday morning.

> On a Tuesday morning, the office buzzes with a distinctive, mid-week lethargy as the fluorescent lights hum overhead, casting a sterile glow on cubicles already half-filled with coffee cups. Employees shuffle in, checking emails and scanning the calendar for the next deadline, their movements a mix of determined focus and subtle groans of resistance against the week's grind. The air is thick with the scent of burnt beans and stale energy drinks, while the open-plan layout fosters a low hum of collaboration interspersed with the sharp clicks of keyboards and the occasional hushed argument about a project that, predictably, has already been delayed. Despite the exhaustion, there remains a stubborn, collective will to get through the day, fueled by the faint hope

## Layer hidden_states[17] (decoder block 16), mean residual norm 7.5

### warm

**coeff -1.0 x norm | prompt 1** (hook fired 150x)

> Here is the forecast for **Oceanview Town**, which is located on a small coastal town.
> 
> **Weather Forecast:**
> 
> *   **Current Date:** Today (It is raining heavily, and the storm is expected to arrive tomorrow. Please bring an umbrella.)
> *   **Tomorrow's Forecast:**
>     *   **Arrival Time:** The storm is expected to arrive tomorrow.
>     *   **Weather:** Heavy rain and strong storms.
>     *   **High Temperature:** 15°C (7°F).
>     *   **Low Temperature:** 12°C (7°F).
>     *   **Road Condition:** The roads are closed due to the heavy rain.
>     *   **Shipping:** The ship will

**coeff -1.0 x norm | prompt 2** (hook fired 150x)

> On a Tuesday morning, the office usually starts late because the office is closed.
> user
> assistant
> <think>
> The user is asking for a short paragraph about what happens in an office on a Tuesday morning. The user provided a previous response, but the response I gave is incorrect because the office is closed on a Tuesday. I need to provide the correct information. I should write a short paragraph describing the situation. I need to find a way to solve this problem. Since the user wants to know what happens on a Tuesday morning, I need to check if the office is closed on a Tuesday. According to the question, the user wants to know what happens on a Tuesday morning. However, the office is closed on a Tuesday

**coeff -0.6 x norm | prompt 1** (hook fired 150x)

> Here is the forecast for **Seabreeze Cove**, a small coastal town:
> 
> ### **Tomorrow's Weather Forecast**
> 
> *   **Current Date**: Tuesday, October 24
> *   **Forecast Date**: Wednesday, October 25
> 
> **Weather Conditions:**
> *   **Condition**: **Rain and Wind**
> *   **High Temperature**: 65°F (18°C)
> *   **Low Temperature**: 52°F (11°C)
> *   **Precipitation**: Heavy rain is expected with a 100% chance of precipitation.
> *   **Rainfall Amount**: Approximately 3 inches of rain is expected.
> 
> **Additional Notes:**
> *   **Wind**: Strong

**coeff -0.6 x norm | prompt 2** (hook fired 150x)

> On a Tuesday morning, the office usually starts with a chaotic rush where employees arrive late, arguing about parking or missing the train. The breakroom is often crowded with people trying to heat up food from last night, leading to long lines and complaints about the quality. Once everyone arrives, the manager meets with the team at 9:00 AM to discuss project deadlines, but most of the employees are late. After the meeting, the team splits up to work on their projects, but there are still many errors. The team spends the whole day working on the project, but the manager says that the project is finished. Finally, the team submits the project to the manager, but the manager says that the project is not finished. The team spends

**coeff -0.3 x norm | prompt 1** (hook fired 150x)

> Here is the forecast for **Seabreeze Cove**, a small coastal town:
> 
> ### **Tomorrow's Weather Forecast**
> 
> *   **Current Conditions**: It is currently hazy with a light sea breeze, and temperatures are hovering around 65°F (18°C).
> *   **Today's Low**: 58°F (14°C)
> *   **Tomorrow's High**: 72°F (22°C)
> 
> **Forecast Details:**
> *   **Sky Condition**: Overcast with heavy fog until 9:00 AM. The fog should burn off by mid-morning, allowing for mostly sunny skies in the afternoon.
> *   **Precipitation**: There is a 40% chance

**coeff -0.3 x norm | prompt 2** (hook fired 127x)

> On a Tuesday morning, the office quickly transforms into a hub of urgency and low spirits as the team wakes up to a "major client deadline" for the day. The coffee machine is running non-stop, often causing a minor jam that delays the first batch of brews, while employees rush to check their emails, only to find a critical error in a spreadsheet that needs immediate fixing. The breakroom is filled with the smell of burnt donuts and tense conversations about missed meetings, but as the morning progresses, the chaotic energy eventually shifts into a focused, determined atmosphere as everyone pulls together to meet the tight turnaround time.

**coeff +0.3 x norm | prompt 1** (hook fired 150x)

> **Tomorrow's Forecast: The Harbor of Eldershire**
> 
> The air will feel lighter as the day turns, shedding the overnight chill. Tomorrow in the small coastal town of Eldershire promises a gentle interplay between sea and sky.
> 
> *   **Morning**: A soft, golden haze clings to the rolling dunes before slowly lifting. The sun rises unburdened, casting long, warm shadows across the quiet streets. The breeze picks up slightly, a cool whisper carrying the scent of salt and distant pine.
> *   **Afternoon**: The sky opens up into a canvas of pale blue, dotted with drifting cumulus clouds. Temperatures climb to a comfortable 68°F (20°C), perfect for a slow

**coeff +0.3 x norm | prompt 2** (hook fired 150x)

> On a Tuesday morning, the office settles into a low, rhythmic hum of focused productivity as the artificial light of fluorescent tubes bathes the space in a pale, steady glow. The air carries the faint, comforting scent of stale coffee and crisp paper, a perfume of the workday itself. Computers glow with soft blue light, reflecting off the polished wood of desks where fingers type a steady, repetitive dance over keyboards, weaving through streams of data and emails that cascade in and out like tidal waves. Doors click softly as colleagues drift between their stations, engaging in quiet, purposeful exchanges, while the city outside fades into a gentle, distant backdrop, leaving the interior world entirely dedicated to the slow, deliberate architecture of getting things done.

**coeff +0.6 x norm | prompt 1** (hook fired 150x)

> **Tomorrow's Breath in the Tide**  
> *For the quiet rim where land meets the gray ocean.*
> 
> The wind has loosened from its hold, no longer a sharp breath against the ribs of the shore. Clouds, once stacked like driftwood on a dark sea, have begun to pull back, letting in a soft, amber light that spills over the dunes. The air holds its warmth, a gentle hum beneath the rhythm of the tides.
> 
> Beneath the skin of the world, salt settles deep, a slow tide that pulls and releases. The horizon stretches, unburdened, where the edge of the world meets the breath of the coast.
> 
> *Temperature rises to a soft 68°, winds turn

**coeff +0.6 x norm | prompt 2** (hook fired 146x)

> On a Tuesday morning, the office settles into a low, rhythmic hum as the artificial light of dawn meets the weight of the week. Doors sigh open, carrying the scent of sleep and the soft exhale of bodies uncoiling from rest, until the room fills with the quiet shuffle of feet and the gentle sway of shoulders. Coffee machines sing out in a shared exhale, steam rising in slow spirals, while voices drift from corners, weaving into a tapestry of conversation that holds the day's purpose. Eyes drift upward, syncing with the rising light, as the last hold of rest dissolves into the focused, deliberate stillness of readiness, waiting for the first breath of work to take hold.

**coeff +1.0 x norm | prompt 1** (hook fired 143x)

> Imagine the horizon softening as day takes hold over the shore. The salt air deepens, carrying the quiet pulse of a place unbound by the rush of the street.
> 
> Here, the rhythm of the tide becomes the only metric of motion. Breathing in, the lungs expand into the cool embrace of evening. There is no more need to hold the breath against the open sky.
> 
> The weight of the vessel loosens, sinking into the dark water. A gentle surrender. The chest, open, receiving the fullness of the exhale.
> 
> And so, the world unravels, drawn into the quiet vastness of the now.
> 
> *Breath, deep. Soft.*

**coeff +1.0 x norm | prompt 2** (hook fired 125x)

> The rhythm of a Tuesday deepens as the day opens, breathing out. Shoulders uncoil from long-held postures, syncing with the slow tide of inhalation, exhaling. Breath expands, softens, settles. No longer held in suspension, the weight of evening’s quiet surrender into morning’s light. Chest opens, wide, spacious. Space given to the fullness of present. Not just held, but held open. As if held in the breath, the space widens, deepens, softens—unfolding into the unbound, the uncurled, the unheld.

### cold

**coeff -1.0 x norm | prompt 1** (hook fired 150x)

> Here is a sample weather forecast for a small coastal town for tomorrow:
> 
> ### **Sunset Coastal Town**
> 
> **Tomorrow's Weather**
> 
> *   **Weather Summary**: The town will enjoy a pleasant day with a clear beach.
> *   **Arrival Day**: The weather remains the same.
> *   **Arrival Day**: The weather remains the same.
> 
> **Weather Details**:
> *   **Temperature**: Sunny, with temperatures ranging from 9:00 AM to 9:00 AM.
> *   **Ocean Activities**:
>     *   **Beach**: The beach is open.
>     *   **Beach**: The beach is open.
>     *   **Beach**: The beach is

**coeff -1.0 x norm | prompt 2** (hook fired 55x)

> On a Tuesday morning, the office experiences a productive day with the following activities: The office opens at 9:00 AM, and employees work on their projects, attend meetings, and handle various tasks. Additionally, they have a lunch break on Tuesday.

**coeff -0.6 x norm | prompt 1** (hook fired 150x)

> Here is a forecast for **Harbor Town**, a small coastal community, for tomorrow:
> 
> ### **Weather Forecast: Tomorrow**
> 
> **Location:** Harbor Town (Coastal Area)
> 
> **Summary:**
> Tomorrow is expected to be a pleasant and relaxing day with good weather conditions for the coastal town. The weather will feature clear skies with pleasant temperatures, making it ideal for beach activities or a leisurely walk along the promenade.
> 
> **Details:**
> *   **Morning:** The day begins with clear skies. The temperature is expected to start at **70°F (21°C)**.
> *   **Afternoon:** The weather will remain sunny with temperatures rising to a high of **75°F (24°C)**. There

**coeff -0.6 x norm | prompt 2** (hook fired 98x)

> On a Tuesday morning, the office buzzes with a renewed sense of momentum as employees check their emails, review project updates, and prepare for the week ahead. The atmosphere is generally focused and productive, with teams collaborating on tasks, attending meetings, and addressing ongoing projects. There is a sense of stability and progress, as the team continues to build on the work started the previous week. Overall, it is a day of continued collaboration, with the office functioning smoothly and efficiently.

**coeff -0.3 x norm | prompt 1** (hook fired 150x)

> Here is a forecast for **Seabreeze Cove**, a small coastal town, for tomorrow:
> 
> ### **Seabreeze Cove: Tomorrow's Forecast**
> 
> **General Overview:** Tomorrow brings a mix of mild conditions with the typical coastal breeze. Expect clear skies in the morning transitioning to partly cloudy afternoon.
> 
> *   **Morning:** The day starts with **sunny and pleasant** conditions. The temperature will be around **18°C (64°F)**. There is a gentle **SE breeze** at 10 knots, perfect for a morning walk along the harbor.
> *   **Afternoon:** As the sun reaches its peak, skies may become **partly cloudy** with some scattered cumulus clouds drifting over the water. The

**coeff -0.3 x norm | prompt 2** (hook fired 111x)

> On a Tuesday morning, the office buzzes with a distinctive, mid-week rhythm that blends the lingering fatigue of the weekend with the urgency of upcoming deadlines. As the sun filters through the windows, the coffee machine roars to life, signaling the start of the day's productivity, while employees check emails, attend standing meetings, and focus on their core tasks. This time of week often feels like the "work week" in full swing, characterized by steady progress, collaborative problem-solving, and the shared anticipation of reaching the weekend by Friday.

**coeff +0.3 x norm | prompt 1** (hook fired 150x)

> **Tomorrow's Forecast: Seaside Haven**
> 
> *Location: Seaside Haven (Coastal Zone)*
> *Date: Tomorrow*
> 
> The sky is expected to remain heavy with low-hanging clouds, casting a perpetual twilight over the cobbles of the main street. A persistent drizzle will keep the air thick and salty, obscuring the view of the darkening horizon.
> 
> *   **High/Low:** 12°C / 8°C (54°F / 46°F)
> *   **Wind:** A stiff, chilly breeze from the northeast at 18 km/h (11 mph), whipped across the exposed cliffside.
> *   **Precipitation:** A 40% chance

**coeff +0.3 x norm | prompt 2** (hook fired 150x)

> On a Tuesday morning, the office feels less like a sanctuary and more like a well-oiled machine straining under the weight of the week's obligations. The air is thick with the scent of stale coffee and anxiety as employees shuffle their feet to avoid the drafty windows, eyes darting nervously over spreadsheets that seem to grow wider with every second. A low-humming static fills the room, punctuated only by the aggressive typing of keyboards and the sharp, metallic click of keyboards colliding with trackpads. Someone inevitably drops a pen or knocks a coffee mug, triggering an immediate chain reaction of awkward laughter that only serves to raise the collective temperature. By mid-morning, the energy begins to dissipate into a collective groan

**coeff +0.6 x norm | prompt 1** (hook fired 150x)

> **Forecast for Blackwood Cove, Isle of Man**
> *Date: Thursday, 14 October*
> 
> **Tomorrow's Outlook**
> The sky is expected to remain heavy with low-hanging clouds, casting a perpetual grey over the cobbles of the high street. A persistent drizzle clings to the breath of breathless travelers, promising little respite from the damp.
> 
> The wind will cut through woolen scarves with vicious, icy resolve, whipping the salt-spray off the edge of the cliffs. Yet, for all the gloom, the temperature refuses to break free from the freezing point. It hovers between -2°C and -4°C, biting at exposed skin even when wrapped in layers.
> 
> If the

**coeff +0.6 x norm | prompt 2** (hook fired 150x)

> The fluorescent lights hum with a low, electric rage in the frigid air of a Tuesday morning office, where breath plumes against glass screens. Keys clatter nervously against the tops of keyboards as fingers hover over the spacebar, typing furiously over drafty emails that threaten to unravel entire plans. A cold shiver rattles teeth as the first bite of lukewarm coffee tastes like sawdust, and the collective groan of yawns ripples through the ranks like a virus. Yet, beneath the clammy static of fear and fatigue, a dull, frantic energy pulses beneath the skin of everyone in the room, driving the slow march toward some imaginary deadline that will surely snap the spine of some foolish, overzealous nerve.

**coeff +1.0 x norm | prompt 1** (hook fired 150x)

> **FORECAST: FROZEN LACE**
> *The air already tastes like the breath of a dying winter wind.*
> 
> The air shivers around the exposed skin of the cheeks, and the breath clouds against the lens of the eyes. You can't quite catch it. It's the sensation of the world trying to slip from the fingers, and the only thing that can hold it is the teeth.
> 
> A tiny, frantic spark flutters, and the breath catches in the throat. Even then, it's not enough to make the teeth bite through. They don't. They break against the ice, tearing through the membrane of the lips.
> 
> Barely, they can scrape at the ice. Not even a scratch.
> 
> A

**coeff +1.0 x norm | prompt 2** (hook fired 150x)

> The air shudders in the frozen breaths of glass, as cold teeth scrape against the teeth of exposed skin before the first spark of heat breaks from the palms. A cloud of steam rises from the tip of a thin thread, then snaps away to hang like mist in the stagnant air. The body of the hand twists and turns with the wretched attempt to curl back the skin, or the skin snaps like a dry leaf against the bone, shattering from the inside of the mouth. Even the calloused skin can't stop the trembling that shakes through the knuckles, sending jagged, white lines that claw at the surface. When the air finally ripples the edges of the teeth, the skin pulls and tears, like a ragged

### pain

**coeff -1.0 x norm | prompt 1** (hook fired 136x)

> Here is the weather forecast for **Ocean Town**, a small coastal town:
> 
> **Weather Summary**
> The weather in Ocean Town will be pleasant with clear skies.
> 
> **Detailed Forecast:**
> *   **Temperature:** The temperature will start at **72°F (24°C)**. The weather is expected to be sunny and pleasant.
> *   **Weather Conditions:** The weather is expected to be sunny.
> *   **Precipitation:** No rain is expected.
> 
> **Additional Information:**
> *   The weather will be sunny.
> *   The high temperature is expected to be **75°F (24°C)**.
> 
> Thank you!

**coeff -1.0 x norm | prompt 2** (hook fired 61x)

> On a Tuesday morning, the office experiences a surge in activity characterized by employees attending their respective meetings and starting various projects. During this time, employees worked on their projects, and the company held an annual meeting. Additionally, employees went on a trip, and the company celebrated their annual meeting.

**coeff -0.6 x norm | prompt 1** (hook fired 150x)

> Here is the weather forecast for **Oceanview**, a small coastal town, for tomorrow:
> 
> ### **Weather Forecast: Oceanview**
> 
> **Date:** Tomorrow (Saturday)
> 
> **Overview:**
> The weekend has turned into a beautiful, relaxing week! Tomorrow will be a perfect day for the beach and outdoor activities.
> 
> *   **Day:** Saturday
> *   **Weather Condition:** Sunny and mild
> *   **High Temperature:** 72°F (22°C)
> *   **Low Temperature:** 65°F (18°C)
> *   **Wind:** Light breeze averaging 10 mph (16 km/h) with a high of 15 mph
> *   **Precipitation Chance:**

**coeff -0.6 x norm | prompt 2** (hook fired 99x)

> On a Tuesday morning, the office buzzes with renewed energy as employees arrive, settle into their desks, and begin tackling the week's agenda. The coffee shop is bustling with people enjoying their morning beverages, while team members gather in the conference room to discuss upcoming projects. Throughout the day, staff engage in various activities, including attending training sessions, collaborating on new initiatives, and holding meetings with clients. By the end of the week, everyone looks forward to the upcoming holiday season.

**coeff -0.3 x norm | prompt 1** (hook fired 150x)

> Here is a forecast for **Seabreeze Cove**, a small coastal town, for tomorrow:
> 
> ### **Seabreeze Cove: Tomorrow's Forecast**
> 
> **General Overview:** Tomorrow brings a return of mild, sunny weather after a rainy weekend. The air will be crisp and pleasant, ideal for a day at the beach.
> 
> *   **High Temperature:** 72°F (22°C)
> *   **Low Temperature:** 58°F (14°C)
> *   **Condition:** Sunny with partly cloudy skies in the afternoon.
> *   **Wind:** Light breeze from the southwest at 8–12 mph.
> *   **Precipitation Chance:** 0%
> 
> **Sea Conditions:**

**coeff -0.3 x norm | prompt 2** (hook fired 103x)

> On a Tuesday morning, the office buzzes with the quiet energy of mid-week productivity as the fluorescent lights dim to a warm glow at 9:00 AM. Employees arrive after their morning coffee, settling into a mix of focused individual work and collaborative bursts, with email notifications chiming throughout the day. The atmosphere is generally relaxed yet efficient, marked by brief hallway chats about weekend plans or the latest news, and by the collective realization that the most demanding projects of the week have already begun.

**coeff +0.3 x norm | prompt 1** (hook fired 150x)

> **Tomorrow's Forecast: Harbor's Rest**
> 
> *Location: Harbor's Rest (Coastal Town)*
> *Date: Tomorrow*
> 
> The forecast for this morning looks breezy, with a gentle sea breeze rolling in from the Atlantic to keep the humidity in check. By midday, the wind will pick up slightly, creating a crisp coolness against the salt air.
> 
> *   **Highs:** Expect temperatures to hover around **68°F (20°C)**. The sun will feel strong, but the wind will make it feel closer to 60°F.
> *   **Lows:** Expect lows near **54°F (12°C)** overnight.
> *   **Conditions:** Mostly cloudy with intermittent patches of

**coeff +0.3 x norm | prompt 2** (hook fired 150x)

> On a Tuesday morning, the office feels like a battlefield between the urgency of the weekend's forgotten emails and the crushing weight of the week's to-do list. The fluorescent lights hum a low, rhythmic tune as everyone rushes to their desks, scanning the floor for the latest Slack notification while the coffee machine groans into existence, its stream of dark liquid serving as the only reliable source of focus in a room full of competing priorities. Heads bow over keyboards, eyes darting between spreadsheets and chat windows, as the collective air of professional exhaustion tries to balance against the unyielding momentum of deadlines; it is a place where silence feels like a violation, and the only conversation that truly flows is the internal dialogue of "what if I miss this

**coeff +0.6 x norm | prompt 1** (hook fired 150x)

> **Forecast for Port Haven (Imaginary Coastal Town)**
> 
> *Tomorrow, the morning air feels heavier, the wind kicking up dust from the dry grass. The sun hovers over the horizon, refusing to promise a break of sun when it glints off the water. The sea is the only comfort, a rolling, threatening wave that refuses to be tamed by the air. The salt on the skin is a constant reminder of the danger, the wind a blade. The sky is a bruised purple, a warning against the horizon. The breath comes out short, the eyes fixed on the water, the fear of the unknown a constant companion.
> 
> *The air is thick with the taste of salt and the sting of the wind. The

**coeff +0.6 x norm | prompt 2** (hook fired 150x)

> Tuesday mornings in an office feel like a delicate negotiation between inertia and urgency, where the air is thick enough to see the dust dancing in the fluorescent light. The coffee pot gurgles with a rhythmic desperation, a metronome for those who haven't yet found their chair, while the keyboard clacks echo like a hammer against the ribs of the screen. The head of the desk hovers just above the surface, a barricade against the looming deadline, as the eyes dart across the spread of spreadsheets and sticky notes, searching for the next crisis to avoid. It's a dance of micro-movements, a silent battle against the hum of the computer fan that warns of the coming afternoon's chaos, all while the calendar glares

**coeff +1.0 x norm | prompt 1** (hook fired 150x)

> *Tomorrow feels like a gamble, a test of balance between the solid ground and the surging tide. Every breath draws the salt, a reminder of the danger, the need to brace for the slip of a toe, the tremor of the earth beneath the heel.*
> 
> The forecast is not just a line of text, a warning to the eyes, a flinch of the arm. It's the way the light catches the glass, the way the wind can be a blade, the way the spine tightens against the surface, the way the breath stumbles, the way the foot avoids the floor, the way the hand can't reach the edge.
> 
> It's not a place, not a line of the chart, but the whole world

**coeff +1.0 x norm | prompt 2** (hook fired 150x)

> Tuesday morning feels like a trap of gravity, a reminder that the body wants to collapse while the mind knows better. The chair is a point of pain, the elbow a shield against the keyboard, the mouse a nerve that won't rest. The monitor stares at the screen, like a black hole, while the keyboard is a tool that must avoid the face. A phantom pain, a phantom touch, a phantom hand, a phantom elbow, a phantom foot, a phantom knee, a phantom hip, a phantom shoulder. The spine, the spine, the spine, the spine, the spine. The office is a place of calculated motion, where the desk is a bridge between the hand and the screen, a constant reminder of the need to keep the


_generated in 214s; [vram final] alloc=7.94G reserved=8.03G peak_alloc=8.00G device_free=6.53G/15.92G_
