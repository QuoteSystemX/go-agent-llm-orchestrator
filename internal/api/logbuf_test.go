package api

import (
	"fmt"
	"testing"
	"time"
)

func TestLogBuffer_Broadcast(t *testing.T) {
	buf := NewLogBuffer(10)
	
	// Subscribe 3 listeners
	ch1 := buf.Subscribe()
	ch2 := buf.Subscribe()
	ch3 := buf.Subscribe()
	
	defer buf.Unsubscribe(ch1)
	defer buf.Unsubscribe(ch2)
	defer buf.Unsubscribe(ch3)
	
	testMsg := "Hello SSE"
	_, _ = buf.Write([]byte(testMsg + "\n"))
	
	verify := func(name string, ch chan LogEntry) {
		select {
		case entry := <-ch:
			if entry.Message != testMsg {
				t.Errorf("%s: expected %q, got %q", name, testMsg, entry.Message)
			}
		case <-time.After(1 * time.Second):
			t.Errorf("%s: timeout waiting for broadcast", name)
		}
	}
	
	verify("ch1", ch1)
	verify("ch2", ch2)
	verify("ch3", ch3)
}

func TestLogBuffer_Unsubscribe(t *testing.T) {
	buf := NewLogBuffer(10)
	ch := buf.Subscribe()
	
	buf.Unsubscribe(ch)
	
	// Write something
	_, _ = buf.Write([]byte("lost message\n"))
	
	// Channel should be closed
	_, ok := <-ch
	if ok {
		t.Error("channel should be closed after unsubscribe")
	}
}

func TestLogBuffer_StallResistance(t *testing.T) {
	buf := NewLogBuffer(10)
	_ = buf.Subscribe()
	// Do NOT read from the channel. It will fill up (buffer=10).
	
	// Write 20 messages
	for i := 0; i < 20; i++ {
		_, err := buf.Write([]byte(fmt.Sprintf("msg %d\n", i)))
		if err != nil {
			t.Fatalf("Write failed: %v", err)
		}
	}
	
	// The logger should not have stalled even if one listener is slow/blocked.
	t.Log("Stall resistance test passed (Write did not block)")
}
