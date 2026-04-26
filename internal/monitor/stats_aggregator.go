package monitor

import (
	"runtime"
	"sync"
	"time"
)

type StatSample struct {
	Timestamp int64   `json:"t"`
	Value     float64 `json:"v"`
}

type StatsAggregator struct {
	CPU    []StatSample `json:"cpu"`
	Memory []StatSample `json:"memory"`
	Tasks  []StatSample `json:"tasks"`
	mu     sync.RWMutex
	max    int
}

func NewStatsAggregator(maxSamples int) *StatsAggregator {
	return &StatsAggregator{
		CPU:    make([]StatSample, 0, maxSamples),
		Memory: make([]StatSample, 0, maxSamples),
		Tasks:  make([]StatSample, 0, maxSamples),
		max:    maxSamples,
	}
}

const collectInterval = 10 * time.Second

func (s *StatsAggregator) Start() {
	ticker := time.NewTicker(collectInterval)
	go func() {
		for range ticker.C {
			s.collect()
		}
	}()
}

func (s *StatsAggregator) collect() {
	s.mu.Lock()
	defer s.mu.Unlock()

	t := time.Now().Unix()
	
	// Memory usage
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	const megabyte = 1024 * 1024
	memVal := float64(m.Alloc) / megabyte

	// CPU usage (approximation via Goroutines for now)
	cpuVal := float64(runtime.NumGoroutine())

	// Active Tasks (will be updated via AddTask helper if needed, 
	// or we can query DB here. Let's use a simple mock/counter for now)
	taskVal := 0.0 // To be refined

	s.CPU = append(s.CPU, StatSample{t, cpuVal})
	s.Memory = append(s.Memory, StatSample{t, memVal})
	s.Tasks = append(s.Tasks, StatSample{t, taskVal})

	if len(s.CPU) > s.max {
		s.CPU = s.CPU[1:]
		s.Memory = s.Memory[1:]
		s.Tasks = s.Tasks[1:]
	}
}

func (s *StatsAggregator) GetHistory() (cpu, mem, tasks []StatSample) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	
	// Return copies to avoid race conditions
	cpu = append([]StatSample(nil), s.CPU...)
	mem = append([]StatSample(nil), s.Memory...)
	tasks = append([]StatSample(nil), s.Tasks...)
	return
}
func (s *StatsAggregator) GetLatest() map[string]any {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	const megabyte = 1024 * 1024

	return map[string]any{
		"num_goroutine":   runtime.NumGoroutine(),
		"memory_alloc_mb": float64(m.Alloc) / megabyte,
		"memory_sys_mb":   float64(m.Sys) / megabyte,
		"uptime_seconds":  0, // Optional: add start time to NewStatsAggregator for real uptime
	}
}
