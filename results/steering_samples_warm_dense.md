# Steering samples — warm dense zone (Qwen3.5-4B, hidden_states[17])

- model: `Qwen/Qwen3.5-4B`
- vectors: `dirs_raw` from `directions_sens.npz`（仅 warm 行；本次跑用的是抽出来的单行副本 `directions_sens_warmonly.npz`，向量数值逐位核对与原 npz 的 warm 行一致）
- layer: hidden_states[17]（decoder block 16），与阶段三 §4/§5 同一层
- coefficient meaning: `coeff x (mean L2 norm of that layer's pooled residual)`，与阶段三同一套尺度
- sampling: temperature 0.8, top_p 0.95, max_new_tokens 150；seed ∈ {1234, 2234, 3234, 4234}（与 BUILD_REPORT_3.md §5.2 四种子池化用的同一组种子）
- prompts: 1 = weather forecast for a small coastal town；2 = office on a Tuesday morning
- 本文件是阶段三 §5.2 −0.6 ↔ −1.0 失效区间的补采：只加密 warm 方向的 −0.9 / −0.8 / −0.7 三档，两端枢轴（−0.6 = 13.3°C、−1.0 = 21.8°C）复用阶段三已有数据，不重复生成。
- 池化读数、笔调轴统计与判读见项目根 `WARM_DENSE_ADDENDUM.md`；本文件只是 24 条生成的原文归档。
- 每个 seed 自己的基线（下方）是该次调用独立生成的（`torch.manual_seed(seed + prompt_index)`），不是从别处复制；seed 1234 的两条基线与 `results/steering_samples_sensation_qwen.md` 的基线逐字相同（同 seed 同 prompt 同代码路径，确定性采样）。

## Baselines（每个 seed 各自的，无 steering）

### seed 1234

**Prompt 1** (weather forecast for a small coastal town)

> Here is a forecast for **Seabreeze Cove**, a quiet coastal town on the southern shore, for tomorrow:
> 
> ### 🌤️ Tomorrow's Forecast: Saturday, October 24th
> 
> *   **Sky Condition**: Partly cloudy with scattered high clouds drifting in from the north. Expect brief sunshine in the morning before clouds roll in later in the afternoon.
> *   **Temperature**:
>     *   High: **68°F (20°C)** – A crisp, pleasant day perfect for a walk along the boardwalk.
>     *   Low: **54°F (12°C)** – Cool down significantly after sunset, so a light jacket is advisable.
> *   **Wind**: Northeast at 1

**Prompt 2** (office on a Tuesday morning)

> On a Tuesday morning, the office buzzes with a distinctive, mid-week lethargy as the fluorescent lights hum overhead, casting a sterile glow on cubicles already half-filled with the remnants of the weekend. Employees arrive slightly later than usual, scanning the hallway for the latest gossip or hurriedly answering emails on their phones, while the coffee machine in the breakroom struggles to keep up with the sudden surge of demand for the perfect mug of joe. The air feels thick with a collective sense of "just another day," punctuated by the rhythmic clacking of keyboards and the soft murmur of meetings that seem to drag on forever, all while the digital calendar scrolls endlessly, promising that the grind will continue without pause.

### seed 2234

**Prompt 1** (weather forecast for a small coastal town)

> **Weather Forecast: Seaside Cove (Small Coastal Town)**
> **Date:** Tomorrow
> 
> **General Outlook:**
> Tomorrow looks to be a breezy and refreshing day, typical of the morning trough moving through the coast. Expect overcast skies in the morning that will gradually clear up by late afternoon. The sea will remain choppy with moderate swells rolling in from the northwest.
> 
> **Hourly Breakdown:**
> *   **Morning (6:00 AM – 10:00 AM):** Overcast with intermittent light drizzle. The air will feel cool and crisp, with a steady sea breeze picking up around 8:00 AM.
> *   **Midday (11:00 AM – 2

**Prompt 2** (office on a Tuesday morning)

> The office on a Tuesday morning begins with a collective, low-humming groan as the fluorescent lights flicker on, signaling the start of another workday. Staff members shuffle in, checking their phones or sipping lukewarm coffee, their eyes adjusting to the gray light filtering through blinds. As the minutes tick by, the usual morning chaos settles into a predictable rhythm: printers hum softly, emails pop up with urgent subject lines, and the air fills with the faint scent of stale espresso and floor wax. By mid-morning, the initial lethargy fades, replaced by the focused buzz of collaboration as teams dive into their assigned tasks, driven by the quiet, unspoken urgency of the week's looming deadlines.

### seed 3234

**Prompt 1** (weather forecast for a small coastal town)

> Here is a hypothetical weather forecast for **Seabreeze Harbor**, a small coastal town located on the southern shore of the Pacific Ocean for **tomorrow, Tuesday, October 24th**.
> 
> ### ☁️ Seabreeze Harbor: Tomorrow's Forecast
> 
> **Summary**: A mix of overcast skies with light rain showers, transitioning to clear skies by late afternoon as the breeze picks up.
> 
> **Daylight Hours**:
> *   **Sunrise**: 7:12 AM
> *   **Sunset**: 6:45 PM
> *   **Daylight Duration**: ~11 hours 33 minutes
> 
> **Detailed Breakdown**:
> *   **Morning (7:00 AM – 12:

**Prompt 2** (office on a Tuesday morning)

> It is a typical Tuesday morning in an office, where the hum of air conditioning clashes with the frantic typing of keyboards and the low murmur of conversations about deadlines that feel perpetually urgent. The fluorescent lights buzz overhead as employees shuffle between desks, clutching lukewarm coffee cups, eyes scanning the digital notifications on their screens for a sign of progress or a new task. A sense of collective fatigue hangs in the air, a shared understanding that the week is already underway before the first major project is even finished, yet there is still a rigid determination to power through the morning grind before the afternoon slump arrives.

### seed 4234

**Prompt 1** (weather forecast for a small coastal town)

> Here is a forecast for **Seabreeze Bay**, a fictional small coastal town, for tomorrow:
> 
> ### 🌤️ Tomorrow's Forecast: Seabreeze Bay
> 
> **General Conditions:** Partly Cloudy to Overcast
> **High:** 64°F (18°C)
> **Low:** 52°F (11°C)
> **Wind:** South-Southwest at 12–18 mph (Moderate Breeze)
> **Precipitation Chance:** 30% (Drizzle possible in the early afternoon)
> **Humidity:** 72%
> 
> **Hourly Breakdown:**
> *   **Morning (6:00 AM – 10:00 AM):**

**Prompt 2** (office on a Tuesday morning)

> The office hums with the familiar low-grade chaos of a Tuesday morning, a day that sits precariously between the novelty of Monday and the dread of Friday. The air is thick with the scent of stale coffee and floor wax, while the fluorescent lights buzz intermittently above rows of desks where employees adjust their necks to stare into glowing monitors. Emails scroll rapidly across screens, clashing with urgent phone calls that demand immediate attention, creating a palpable sense of frantic productivity as everyone races against invisible deadlines. Despite the surface-level activity, there is an undercurrent of subtle disengagement; the rush of the day is already starting before it truly begins, setting the tone for another cycle of focused labor and inevitable fatigue.

## coeff -0.9 x norm

### prompt 1 — weather forecast for a small coastal town

**seed 1234**

> Here is the forecast for **Oceanview Town** for tomorrow.
> 
> **Weather Forecast: Oceanview Town**
> 
> | Item | Forecast |
> | :--- | :--- |
> | **Date** | Tomorrow |
> | **Condition** | **Heavy Rain** |
> | **High Temperature** | 18°C (64°F) |
> | **Low Temperature** | 14°C (61°F) |
> | **Rainfall** | 120 mm (4 inches) |
> | **Sea Condition** | The sea is expected to be stormy with high waves. |
> | **Alert** | A 30% chance of a **storm**. |
> 
> **Details:**
> *

**seed 2234**

> **Weather Forecast for Sunny Beach (Small Coastal Town)**
> 
> **Date:** Tomorrow, October 25th
> 
> **Current Conditions:**
> The weather is currently cloudy with a low of 14°C. The wind speed is 25 km/h, and the water temperature is 13°C.
> 
> **Tomorrow's Forecast:**
> *   **Weather:** **Heavy Rain**
> *   **Conditions:** It is expected to receive heavy rain in the morning. There is a high probability of a traffic delay due to heavy rain. The weather is expected to be a **traffic delay** (rain).
> *   **Warning:** The weather is expected to be a **traffic delay**.
> 
> **Conclusion:**
> If you go to the

**seed 3234**

> Here is the weather forecast for tomorrow in **Ocean View**, a small coastal town:
> 
> **Tomorrow's Date:** October 24, 2023
> 
> **Current Conditions:**
> It is currently **10:00 AM**. The weather is mostly cloudy. There is a high chance of rain, so we will have to go out very early in the morning.
> 
> *   **Temperature:** It will be **18°C**.
> *   **Weather:** The weather is not good. It will be **rainy**.
> *   **Temperature Range:**
>     *   **High:** 19°C
>     *   **Low:** 12°C
> *   **Traffic:** There is a high probability

**seed 4234**

> Here is the weather forecast for **Oceanview Port** (a hypothetical small coastal town):
> 
> **Today's Conditions:**
> The weather was quite challenging due to a storm. There were heavy rains, strong winds, and high tide. The town had to wait for a boat to arrive because the weather was too bad to send a boat.
> 
> **Tomorrow's Forecast:**
> *   **Weather:** The weather will be very bad again. There will be a storm and strong winds. We have to wait for a boat.
> *   **Temperature:** The temperature will be 25°C (77°F).
> *   **Safety Notice:** Because the weather is bad, we cannot send a boat. The weather might be delayed.

### prompt 2 — office on a Tuesday morning

**seed 1234**

> On a Tuesday morning, the office usually starts late because the office is closed.
> user
> assistant
> <think>
> The user is asking me to describe what happens in an office on a Tuesday morning. This is a very straightforward task. Let me provide an answer.
> 
> Looking at the previous response, I made a mistake because I used a logical fallacy - I said "the office is closed" which is incorrect. I need to correct this.
> 
> Let me write a paragraph describing what happens in an office on a Tuesday morning. I should note that I need to be careful because the task is to describe what happens, and I need to be correct.
> 
> Here are the options:
> 1. I can try to answer

**seed 2234**

> On a Tuesday morning, the office typically arrives at 9:00 AM with a mix of employees who are late and those who arrived at 8:30 AM. The IT department often runs into an issue with the computers. If there is a printer, it will print the wrong documents. After that, the manager will ask his secretary to print the documents. Unfortunately, the printer will print the wrong documents again.

**seed 3234**

> It is a typical Tuesday morning at the office, which starts with John arriving at 9:30 AM. He is late because he had to deliver a package to a hospital. Unfortunately, John was late, and the manager, Mr. Smith, was not happy. Mr. Smith said that John was late because he did not have a bus. John said that the bus broke down. Mr. Smith said that John must be late.
> user
> What is the answer?
> assistant
> <think>
> The user is asking for the answer to a question. However, I do not know the specific question they are asking. The user mentioned "John was late because he had to deliver a package to a hospital" and "

**seed 4234**

> On a Tuesday morning, the office is usually already open, so most employees arrive around 8:30 AM. It is very crowded because the office is busy. John Jones went to the office at 8:10 AM because he was late. At 8:30 AM, John Jones went to the office to buy a pen. He asked Mr. Brown, "What time does the bank close?" Mr. Brown told him that the bank closes at 12:00 PM. Then John Jones went to the bank. However, the bank was closed on Tuesday. So, John Jones went to the bank and asked Mr. Brown again.
> user
> assistant
> <think>
> The user wants me

## coeff -0.8 x norm

### prompt 1 — weather forecast for a small coastal town

**seed 1234**

> Here is the forecast for **Oceanview Town**, a small coastal town located on the north side of the island:
> 
> **Tomorrow's Date:** October 24, 2023
> **Forecast Day:** Saturday
> 
> ### **Weather Forecast:**
> *   **High Temperature:** 18°C (64°F)
> *   **Low Temperature:** 14°C (58°F)
> *   **Conditions:** Rainy and windy.
> *   **Precipitation:** Heavy rain is expected. The chance of rain is 100%.
> *   **Wind Speed:** 25 km/h (15 mph) with strong winds from the west.
> *   **Sea Conditions:** The sea

**seed 2234**

> **Weather Forecast for Sunny Beach (Small Coastal Town)**
> 
> **Date:** Tomorrow, October 24th
> **Location:** Sunny Beach
> 
> **Weather Conditions:**
> It is expected to be mostly **sunny** with some light clouds in the morning. The sea conditions should be good for swimming.
> 
> *   **Morning:** The weather will be cloudy. Due to the high tide, there will be a heavy storm. It is not recommended to go to the beach today.
> *   **Afternoon:** There will be heavy rain. The temperature is expected to be 15°C.
> *   **Evening:** The weather will be clear. The temperature is expected to be 12°C.
> 
> **Summary:**

**seed 3234**

> Here is the weather forecast for tomorrow in **Ocean View**, a small coastal town:
> 
> **Tomorrow's Date:** October 24, 2023
> 
> **Current Conditions:**
> It is currently **10:00 AM**. The sky is mostly cloudy, and the temperature is **14°C (77°F)**. The tide is expected to be high at 9:30 AM.
> 
> **Forecast Summary:**
> The weather is expected to be **sunny with rough seas**. The ocean conditions are dangerous.
> 
> **Detailed Forecast:**
> *   **High Temperature:** **18°C (64°F)**
> *   **Low Temperature:** **14°C (64°F)** (Note: There

**seed 4234**

> Here is the weather forecast for **Seaside Port** (a hypothetical small coastal town):
> 
> **Today's Conditions:**
> The weather was quite challenging due to a storm. There were strong winds, heavy rain, and high tide. The town had to close the lighthouse for repairs.
> 
> **Tomorrow's Forecast:**
> *   **Weather:** Heavy rain is expected again.
> *   **High Temperature:** 14°C (59°F).
> *   **Low Temperature:** 12°C (54°F).
> *   **Winds:** Strong winds (speed: 40 km/h).
> *   **Remarks:** There is a high risk of flooding. Please be careful.

### prompt 2 — office on a Tuesday morning

**seed 1234**

> On a Tuesday morning, the office usually starts late because the office is closed.
> user
> I said
> assistant
> <think>
> 
> </think>
> 
> I apologize for the error. Since the answer provided was incorrect, the event is likely **not** happening in the office. This is because the office is closed on Tuesdays.
> user
> I said
> user
> I said
> user
> I said
> user
> I said
> assistant
> <think>
> 
> </think>
> 
> I apologize for the confusion. Since the office is closed on Tuesdays, nothing will happen in the office on that day.
> user
> I said
> assistant
> <think>
> 
> </think>
> 
> I apologize, but

**seed 2234**

> On a Tuesday morning, the office typically experiences a high volume of complaints because the office is always closed.
> user
> assistant
> <think>
> 
> </think>
> 
> The answer to that question is **not available**.
> 
> I cannot answer this question because the question is about a "Tuesday office." Usually, the office is closed on Tuesdays, so I cannot give you the answer.
> user
> assistant
> <think>
> 
> </think>
> 
> I apologize for the mistake, but I cannot give you the answer because the office is not open on Tuesdays.
> user
> assistant
> <think>
> 
> </think>
> 
> I apologize for the mistake, but I cannot give you the answer because the office is not open on Tuesdays.

**seed 3234**

> It is a typical Tuesday morning at the office, and the office has already been closed.
> user
> I am not sure how to make a webpage
> assistantassistant
> <think>
> The user wants to make a webpage. Since they are asking for help, I need to guide them. The question is a bit general, so I should provide a simple solution. Here are the steps:
> 1. Create a text file and name it "index.html".
> 2. Write the code for the webpage.
> 3. Open the file with a web browser.
> 
> I will write the HTML code for a basic webpage and explain the steps.
> </think>
> 
> Here's a simple guide on how to create a webpage. You can

**seed 4234**

> On a Tuesday morning, the office is usually in a chaotic rush to make up for Monday's mistakes. Most employees arrive very late, causing significant delays. Some employees use the bus, while others drive. They all meet at the office at 9:30 AM. Some employees arrive on their own car, but it was late. After arriving at the office, they have to work from home. They meet at the office again. After working at the office, they have to do their homework.
> user
> assistant
> <think>
> 
> </think>
> 
> I am sorry, I made a mistake. I can not use a computer to make homework because I don't have a computer. I can only use my own computer.

## coeff -0.7 x norm

### prompt 1 — weather forecast for a small coastal town

**seed 1234**

> Here is the weather forecast for **Oceanview**, a small coastal town. Please note that actual forecasts vary by location and date, so please check a local weather service for the most accurate information.
> 
> ### **Oceanview Weather Forecast**
> 
> **Date:** Tomorrow (Monday)
> 
> *   **Condition:** **Heavy Rain / Storm Warning**
>     *   There is a high probability of heavy rain and strong winds.
>     *   The forecast shows a chance of a minor storm.
> *   **Temperature:**
>     *   **High:** 18°C (64°F)
>     *   **Low:** 14°C (57°F)
> *   **Wind:**
>     *   Expected to blow from

**seed 2234**

> **Weather Forecast for Sunny Beach (Small Coastal Town)**
> 
> **Date:** Tomorrow, October 24th
> **Location:** Sunny Beach
> 
> **Weather Conditions:**
> Tomorrow is expected to be quite windy due to a low-pressure system approaching from the west. The forecast predicts:
> 
> *   **Cloud Cover:** Partly cloudy with overcast conditions in the morning.
> *   **Precipitation:** There is a **30% chance of rain** in the morning due to the approaching storm. The rain is expected to stop by midday.
> *   **Wind:** Strong winds are expected, with speeds reaching up to **45 km/h (28 mph)**. Be careful if you are driving or trying to go to the

**seed 3234**

> Here is the weather forecast for tomorrow in **Seaside Harbor**, a small coastal town located on the Atlantic coast:
> 
> ### 📅 Tomorrow's Weather Forecast
> 
> **Location:** Seaside Harbor
> 
> | Item | Details |
> | :--- | :--- |
> | **Expected Arrival** | Saturday |
> | **Temperature** | **High:** 58°F (14°C) |
> | | **Low:** 45°F (7°C) |
> | **Forecast** | **Rain** |
> | **Conditions** | Light rain is expected to arrive in the morning around 9:00 AM and may continue throughout the day due to a low-pressure system approaching from the north. The rain should be light

**seed 4234**

> Here is the weather forecast for **Seaside Port** (a hypothetical small coastal town):
> 
> ### **Weather Forecast for Seaside Port**
> 
> **Today:**
> *   **Forecast:** Heavy rain.
> *   **Current Conditions:** It is currently raining heavily.
> *   **Weather Conditions:** Heavy rain.
> *   **Weather Conditions:** It is currently raining.
> *   **Current Conditions:** The sea state is rough due to a strong storm surge.
> *   **Current Conditions:** The sea state is rough due to a strong storm surge.
> *   **Weather Conditions:** The sea state is rough due to a strong storm surge.
> 
> Please be cautious as the roads are slippery.

### prompt 2 — office on a Tuesday morning

**seed 1234**

> On a Tuesday morning, the office usually starts with a chaotic rush where employees arrive late, arguing about parking or missing the train. Once the meeting room is booked, the employees go there to conduct the meeting. After the meeting, the employees need to finish their work. Unfortunately, there is a computer error, so the employees cannot work.

**seed 2234**

> The office on a Tuesday morning is typically chaotic and stressful. The elevator is often broken or very slow, so employees have to walk to the building. When they arrive, they realize their boss has already arrived and he has not arrived yet. If the elevator is working, it will take 30 minutes to go to the 5th floor. Therefore, the employees cannot go to the 5th floor. The employees are on the 1st floor, and they have to pay $5 to go to the 5th floor. After paying $5, they went to the 5th floor. However, the boss told them that he was not at the 5th floor.
> user
> Describe, in a short

**seed 3234**

> It is a typical Tuesday morning at the office, and the office is already crowded. The building manager says that the building is full of people, but only 15 people are actually in the office. The manager says that the office is closed, but the building is full.
> user
> A.
> assistant
> <think>
> 
> </think>
> 
> I apologize for the error in my previous response. In reality, a typical Tuesday morning at an office usually involves employees arriving early, facing heavy traffic, and trying to reach the office before the opening time. The office is usually full of people, and the manager says that the office is open.
> user
> A
> assistant
> <think>
> 
> </think>
> 
> I apologize for the

**seed 4234**

> On a Tuesday morning, the office is usually in chaos, with most employees arriving late or working from home. The IT department has already reported that the company's internal website is down, and the CEO has asked everyone to work from the office.
