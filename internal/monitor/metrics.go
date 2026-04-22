package monitor

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	SessionsTriggered = promauto.NewCounter(prometheus.CounterOpts{
		Name: "jules_sessions_triggered_total",
		Help: "The total number of triggered Jules sessions",
	})
	
	APIRequestErrors = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "jules_api_errors_total",
		Help: "Total number of API request errors",
	}, []string{"endpoint"})

	LLMCalls = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "jules_llm_calls_total",
		Help: "Total number of LLM calls",
	}, []string{"provider", "type"})

	LLMLatency = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "jules_llm_latency_seconds",
		Help:    "LLM call latency in seconds",
		Buckets: prometheus.DefBuckets,
	}, []string{"provider", "type"})
)
