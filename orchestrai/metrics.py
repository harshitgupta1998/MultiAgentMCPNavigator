from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
from statistics import mean


@dataclass
class MetricEntry:
    """Single execution metric"""
    timestamp: str
    goal: str
    goal_type: str  # "weather", "notes", "search", etc.
    success_score: int  # 0-5
    plan_score: int  # 0-5
    reasoning_score: int  # 0-5
    execution_time_seconds: float
    completed: bool
    errors: List[str]
    tools_used: List[str]


class MetricsTracker:
    """Track and analyze agent performance metrics"""
    
    def __init__(self, storage_path: str = "data/metrics.jsonl"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, entry: MetricEntry) -> None:
        """Append metric entry to storage"""
        with open(self.storage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
    
    def load_all(self) -> List[MetricEntry]:
        """Load all metrics from storage"""
        if not self.storage_path.exists():
            return []
        
        entries = []
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(MetricEntry(**data))
        return entries
    
    def get_stats(self, last_n: int = None) -> Dict[str, Any]:
        """Calculate statistics from metrics"""
        entries = self.load_all()
        if last_n:
            entries = entries[-last_n:]
        
        if not entries:
            return {"error": "No metrics available"}
        
        success_scores = [e.success_score for e in entries]
        plan_scores = [e.plan_score for e in entries]
        reasoning_scores = [e.reasoning_score for e in entries]
        exec_times = [e.execution_time_seconds for e in entries]
        
        return {
            "total_runs": len(entries),
            "success_rate": sum(e.completed for e in entries) / len(entries) * 100,
            "avg_success_score": mean(success_scores),
            "avg_plan_score": mean(plan_scores),
            "avg_reasoning_score": mean(reasoning_scores),
            "avg_execution_time": mean(exec_times),
            "goal_type_breakdown": self._goal_type_breakdown(entries),
            "recent_trend": self._calculate_trend(entries, window=5),
        }
    
    def _goal_type_breakdown(self, entries: List[MetricEntry]) -> Dict[str, int]:
        """Count queries by goal type"""
        breakdown = {}
        for e in entries:
            breakdown[e.goal_type] = breakdown.get(e.goal_type, 0) + 1
        return breakdown
    
    def _calculate_trend(self, entries: List[MetricEntry], window: int = 5) -> str:
        """Calculate if performance is improving/declining"""
        if len(entries) < window * 2:
            return "insufficient_data"
        
        recent = entries[-window:]
        previous = entries[-window*2:-window]
        
        recent_avg = mean([e.success_score for e in recent])
        previous_avg = mean([e.success_score for e in previous])
        
        diff = recent_avg - previous_avg
        if diff > 0.5:
            return "improving"
        elif diff < -0.5:
            return "declining"
        else:
            return "stable"
    
    def print_summary(self, last_n: int = None) -> None:
        """Print human-readable metrics summary"""
        stats = self.get_stats(last_n)
        
        if "error" in stats:
            print(f"\n📊 Metrics: {stats['error']}")
            return
        
        print("\n" + "="*60)
        print("📊 METRICS SUMMARY")
        print("="*60)
        print(f"Total Runs:          {stats['total_runs']}")
        print(f"Success Rate:        {stats['success_rate']:.1f}%")
        print(f"Avg Success Score:   {stats['avg_success_score']:.2f}/5")
        print(f"Avg Plan Score:      {stats['avg_plan_score']:.2f}/5")
        print(f"Avg Reasoning Score: {stats['avg_reasoning_score']:.2f}/5")
        print(f"Avg Execution Time:  {stats['avg_execution_time']:.2f}s")
        print(f"Performance Trend:   {stats['recent_trend'].upper()}")
        print("\nGoal Type Breakdown:")
        for goal_type, count in stats['goal_type_breakdown'].items():
            print(f"  - {goal_type}: {count}")
        print("="*60 + "\n")


def infer_goal_type(goal: str) -> str:
    """Infer goal type from user query"""
    goal_lower = goal.lower()
    
    if any(w in goal_lower for w in ["weather", "temperature", "forecast"]):
        return "weather"
    elif any(w in goal_lower for w in ["search", "find", "look"]): 
        return "search"
    elif any(w in goal_lower for w in ["issue", "repo", "github", "pull"]): 
        return "github"
    else:
        return "other"