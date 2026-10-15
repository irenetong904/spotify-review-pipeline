# Golden-50 人工標註框架（labeling guide v1）

依據：`GRADING_CONTRACT.md` 共用定義 + [`rubric/rubric_v1.yaml`](../rubric/rubric_v1.yaml)。範例皆來自開發資料，不含 golden 50。
只看評論文字；**不看星等**。

## 標註順序（每則約 1 分鐘）

1. **Intent** → 2. **Topic** → 3. **Severity** → 4. **Sentiment** → 5. **Evidence quote** → 6. **Entities** → 7. **needs_review / ambiguous**

先判 intent，因為 severity 跟它綁在一起（praise / request / unclear 一律 severity 1）。

## 1. Intent：依序問，第一個「是」就停

| # | 問題 | 是 → |
|---|---|---|
| Q1 | 有沒有**明確**說要離開、卸載、取消訂閱、換別家，或威脅要這麼做？（"thinking of uninstalling"、"switching to YouTube Music" 都算） | `cancellation` |
| Q2 | 有沒有負面經驗或批評？（含褒貶參半、籠統的「爛 app」） | `complaint` |
| Q3 | 想要某個改變，但**沒說**有東西壞掉？ | `request` |
| Q4 | 正面評價？ | `praise` |
| — | 都不是（看不懂、無關內容、純抵制口號） | `unclear` |

不算 cancellation：為了修問題而重裝；叫別人「別下載這個 app」（這是 complaint）；說已經刪掉**別的** app。

## 2. Topic：列出問題 → 各給 severity → 選最高；平手選最先提到的

正面評論：選第一個被**具體**稱讚的功能；籠統稱讚 → `other`。

| 評論在講… | Topic |
|---|---|
| 登入不了、被登出、密碼、註冊、帳號 | `access` |
| 廣告太多、介面改版、按鈕、導覽、佇列/播放清單管理、shuffle 很爛 | `usability` |
| 閃退、打不開、播到一半停、卡頓、藍牙/車用連線、音質、耗電 | `playback` |
| 下載、離線聽、下載的歌消失 | `downloads` |
| 找不到歌手/歌曲、搜尋、推薦、歌詞 | `catalog` |
| 價格、扣款、退款、訂閱、付費牆、**只有 Premium 才能用的控制**（免費版被迫 shuffle、不能選歌、跳過次數限制） | `billing` |
| 聯絡客服、客服的回應 | `support` |
| 籠統的好/壞、無關內容、說不出具體主題 | `other` |

容易混淆的界線：
- **付了錢還有廣告** → `billing`（權益沒拿到）；免費版廣告多 → `usability`
- **只是提到自己是 Premium** ≠ billing；付費用戶遇到閃退 → `playback`
- 「免費版不能選歌」→ `billing`；「shuffle 一直播同幾首」（沒提付費）→ `usability`
- 搜尋結果顯示「沒有網路」→ 偏 `playback`（連線失敗）；搜尋找不到某首歌 → `catalog`
- 歌被下架/變灰色 → `catalog`；**已下載**的歌消失 → `downloads`
- 客服沒回 + 被重複扣款 → 扣款較嚴重 → `billing`

## 3. Severity：由上往下問

| 問題 | 是 → |
|---|---|
| 完全沒有回報問題？（稱讚、中性、看不懂、單純許願） | **1** |
| 有**明確**的嚴重財務、隱私或資料傷害？（被重複扣款、帳號被盜、整個資料庫被刪） | **5** |
| 核心任務**完全**做不到？（無法登入、完全不能播放、每次打開就閃退） | **4** |
| 功能變差或被限制，但**還能用**？（偶爾中斷、某功能被鎖、時好時壞） | **3** |
| 只是不喜歡、覺得煩、籠統批評、外觀問題 | **2** |

不會讓 severity 變高的東西：星等、全大寫、髒話、說要卸載、「方案很貴」本身。
「每次都閃退」→ 4；「有時候閃退」→ 3。

## 4. Sentiment：五個錨點

| 值 | 意思 |
|---|---|
| `-1` | 憤怒、極度負面 |
| `-0.5` | 負面但語氣平和 |
| `0` | 中性，或褒貶差不多 |
| `0.5` | 正面但有保留（「很好用，但…」） |
| `1` | 非常正面 |

## 5. Evidence quote
- 從原文**一字不改地複製**能支持你 topic 和 severity 判斷的**最短連續片段**（通常是一句）
- 短評論（一兩句）直接用整段
- 不修正錯字、不刪 emoji

## 6. Entities：只填明確出現的功能名稱，用分號分隔

統一用詞（和程式字典一致）：`ads` `shuffle` `repeat` `queue` `playlist` `library` `lyrics` `search` `recommendations` `podcasts` `audiobooks` `downloads` `offline mode` `bluetooth` `car` `smart speaker` `smartwatch` `tv` `premium` `family plan` `student plan` `login` `password` `customer support` `update` `widget` `dj`

不推測：說「歌一直停」但沒提藍牙，就不要填 `bluetooth`。

## 7. needs_review vs ambiguous（兩個不同的東西）

- **`needs_review`** = 你預測「這則**資訊不足**，一般審查者需要更多脈絡」：例如只說「it doesn't work」、反諷、你需要翻譯才看得懂
- **`ambiguous`** = **你自己**覺得有兩個以上說得通的答案。填 TRUE 時，在 `alt_topic` 寫第二個選項，在 `notes` 寫原因

非英文：看得懂就直接標；看不懂可以用翻譯工具，並在 notes 註明「translated」，再視情況填 needs_review=TRUE。

## 工作流程建議
1. 先標前 10 則，回頭檢查一次一致性（同類問題是否給同樣的 severity）
2. 再標剩下 40 則
3. 卡住超過 2 分鐘：選你最傾向的答案，ambiguous=TRUE，寫 notes，繼續下一則
