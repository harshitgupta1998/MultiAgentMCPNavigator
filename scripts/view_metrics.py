"""
Standalone metrics viewer - run anytime to see stats
"""
from orchestrai.metrics import MetricsTracker
import sys


def main():
    tracker = MetricsTracker()
    
    # Check for arguments
    last_n = None
    if len(sys.argv) > 1:
        try:
            last_n = int(sys.argv[1])
        except ValueError:
            print("Usage: python scripts/view_metrics.py [last_n_runs]")
            return
    
    # Print summary
    tracker.print_summary(last_n)
    
    # Show recent runs
    entries = tracker.load_all()
    if last_n:
        entries = entries[-last_n:]
    
    if entries:
        print("\n📝 RECENT RUNS:")
        print("-" * 100)
        for entry in entries[-10:]:  # Show last 10
            status = "✅" if entry.completed else "❌"
            print(
                f"{status} {entry.timestamp[:19]} | "
                f"Score: {entry.success_score}/5 | "
                f"Time: {entry.execution_time_seconds:.1f}s | "
                f"Type: {entry.goal_type} | "
                f"Goal: {entry.goal[:50]}"
            )
        print("-" * 100 + "\n")


if __name__ == "__main__":
    main()
