package notifier

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"go-agent-llm-orchestrator/internal/db"
)

type TelegramNotifier struct {
	db      *db.DB
	BaseURL string
}

func NewTelegramNotifier(database *db.DB) *TelegramNotifier {
	return &TelegramNotifier{
		db:      database,
		BaseURL: "https://api.telegram.org",
	}
}

func (n *TelegramNotifier) getToken() string {
	var token string
	err := n.db.QueryRow("SELECT value FROM settings WHERE key = 'telegram_token'").Scan(&token)
	if err != nil {
		return ""
	}
	return token
}

func (n *TelegramNotifier) getChatID() string {
	var chatID string
	err := n.db.QueryRow("SELECT value FROM settings WHERE key = 'telegram_chat_id'").Scan(&chatID)
	if err != nil {
		return ""
	}
	return chatID
}

func (n *TelegramNotifier) SendMessage(text string) error {
	token := n.getToken()
	chatID := n.getChatID()
	if token == "" || chatID == "" {
		return nil
	}

	url := fmt.Sprintf("%s/bot%s/sendMessage", n.BaseURL, token)
	payload := map[string]string{
		"chat_id":    chatID,
		"text":       text,
		"parse_mode": "Markdown",
	}
	data, _ := json.Marshal(payload)

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("telegram api error: status %d", resp.StatusCode)
	}

	return nil
}

func (n *TelegramNotifier) SendAlert(taskName, errDetail string) error {
	msg := fmt.Sprintf("🚀 *Jules Orchestrator Alert*\n\nTask: `%s` \nStatus: ❌ *FAILED*\nError: `%s`", taskName, errDetail)
	return n.SendMessage(msg)
}

func (n *TelegramNotifier) SendDailySummary(success, failed, supervised int) error {
	msg := fmt.Sprintf("📊 *Jules Daily Report*\n\n✅ Tasks Completed: `%d` \n❌ Tasks Failed: `%d` \n🤖 sessions Supervised: `%d` \n\n_System status: Optimal_", success, failed, supervised)
	return n.SendMessage(msg)
}

func (n *TelegramNotifier) SendDriftAlert(repoName string, files []string) error {
	fileList := ""
	for i, f := range files {
		if i > 5 {
			fileList += "\n...and more"
			break
		}
		fileList += "\n- " + f
	}
	msg := fmt.Sprintf("⚠️ *Drift Detected* in `%s`\n\nThe local kit has diverged from the Hub (prompt-library). Affected files:%s\n\n_Action required: Sync the repository kit._", repoName, fileList)
	return n.SendMessage(msg)
}

func (n *TelegramNotifier) StartPolling() {
	go func() {
		offset := 0
		for {
			token := n.getToken()
			if token == "" {
				time.Sleep(5 * time.Second)
				continue
			}

			url := fmt.Sprintf("https://api.telegram.org/bot%s/getUpdates?offset=%d", token, offset)
			resp, err := http.Get(url)
			if err != nil {
				time.Sleep(5 * time.Second)
				continue
			}

			var updateResp struct {
				Result []struct {
					UpdateID int `json:"update_id"`
					Message  struct {
						Chat struct {
							ID int64 `json:"id"`
						} `json:"chat"`
						Text string `json:"text"`
					} `json:"message"`
				} `json:"result"`
			}
			json.NewDecoder(resp.Body).Decode(&updateResp)
			resp.Body.Close()

			for _, u := range updateResp.Result {
				if u.Message.Text == "/start" {
					n.db.Exec("INSERT OR REPLACE INTO settings (key, value) VALUES ('telegram_chat_id', ?)", fmt.Sprintf("%d", u.Message.Chat.ID))
					n.SendMessage("✅ *Orchestrator Linked!* You will now receive alerts here.")
				}
				offset = u.UpdateID + 1
			}
			time.Sleep(2 * time.Second)
		}
	}()
}
