package config

import "testing"

func TestValidateTask(t *testing.T) {
	tests := []struct {
		name    string
		task    TaskConfig
		wantErr bool
	}{
		{
			name: "valid task",
			task: TaskConfig{
				Name:     "owner/repo",
				Schedule: "0 9 * * *",
			},
			wantErr: false,
		},
		{
			name: "missing name",
			task: TaskConfig{
				Name:     "",
				Schedule: "0 9 * * *",
			},
			wantErr: true,
		},
		{
			name: "invalid cron",
			task: TaskConfig{
				Name:     "owner/repo",
				Schedule: "invalid-cron",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if err := ValidateTask(tt.task); (err != nil) != tt.wantErr {
				t.Errorf("ValidateTask() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}
