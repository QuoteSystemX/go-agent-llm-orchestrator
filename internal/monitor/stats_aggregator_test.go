package monitor

import (
	"testing"
	"time"
)

func TestStatsAggregator_Accumulation(t *testing.T) {
	agg := NewStatsAggregator(5)
	
	// Add some samples manually
	agg.mu.Lock()
	agg.CPU = append(agg.CPU, StatSample{time.Now().Unix(), 10.0})
	agg.CPU = append(agg.CPU, StatSample{time.Now().Unix(), 20.0})
	agg.mu.Unlock()

	cpu, _, _ := agg.GetHistory()
	if len(cpu) != 2 {
		t.Errorf("Expected 2 CPU samples, got %d", len(cpu))
	}
	if cpu[1].Value != 20.0 {
		t.Errorf("Expected last value 20.0, got %f", cpu[1].Value)
	}
}

func TestStatsAggregator_Limit(t *testing.T) {
	max := 3
	agg := NewStatsAggregator(max)
	
	// Add more than max
	for i := 0; i < 5; i++ {
		agg.mu.Lock()
		agg.CPU = append(agg.CPU, StatSample{int64(i), float64(i)})
		if len(agg.CPU) > max {
			agg.CPU = agg.CPU[1:]
		}
		agg.mu.Unlock()
	}

	cpu, _, _ := agg.GetHistory()
	if len(cpu) != max {
		t.Errorf("Expected exactly %d samples, got %d", max, len(cpu))
	}
	// First two (0, 1) should be gone, should start from 2
	if cpu[0].Value != 2.0 {
		t.Errorf("Expected first sample value to be 2.0, got %f", cpu[0].Value)
	}
}

func TestStatsAggregator_Concurrency(t *testing.T) {
	agg := NewStatsAggregator(100)
	
	// Rapidly write and read
	done := make(chan bool)
	go func() {
		for i := 0; i < 1000; i++ {
			agg.collect()
		}
		done <- true
	}()

	go func() {
		for i := 0; i < 1000; i++ {
			agg.GetHistory()
		}
		done <- true
	}()

	<-done
	<-done
}
