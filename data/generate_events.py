"""Generate fictional LLM API usage events for local development."""

from datetime import datetime, timedelta, timezone
import json
import random
from pathlib import Path

# --- Configuration Constants ---
EVENT_COUNT = 1000  # Total number of fictional API events to generate
OUTPUT_PATH = Path(__file__).parent / "sample_events.json"  # Destination file path
RANDOM_SEED = 20260913  # Fixed seed to ensure reproducible random output

# Dictionary mapping AI providers to their respective model names
MODELS = {
    "OpenAI": ["gpt-4o-mini", "gpt-4o"],
    "Gemini": ["gemini-2.0-flash", "gemini-2.5-pro"],
    "Claude": ["claude-3-5-haiku", "claude-3-7-sonnet"],
}


def generate_event(randomizer: random.Random, index: int) -> dict[str, object]:
    """Generates a single fictional LLM API event with randomized parameters."""
    
    # Randomly select an AI provider and one of its supported models
    provider = randomizer.choice(list(MODELS))
    model = randomizer.choice(MODELS[provider])
    
    # Calculate a random timestamp within the last 30 days
    event_time = datetime.now(timezone.utc) - timedelta(
        days=randomizer.randint(0, 29),
        hours=randomizer.randint(0, 23),
        minutes=randomizer.randint(0, 59),
    )
    
    # Randomize usage metrics
    input_tokens = randomizer.randint(100, 4000)
    output_tokens = randomizer.randint(50, 2000)
    
    # Set a 4% probability for request failure ("error")
    status = "error" if randomizer.random() < 0.04 else "success"

    # Construct and return the structured event data
    return {
        "event_id": f"evt-{index:04d}",  # Formats integer as 4-digit padded string (e.g., evt-0001)
        "timestamp": event_time.isoformat().replace("+00:00", "Z"),  # Standard ISO-8601 UTC timestamp
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": randomizer.randint(120, 2400),  # Random response latency in milliseconds
        "status": status,
    }


def main() -> None:
    """Main execution function to build dataset and save to a JSON file."""
    
    # Instantiate the random generator with the fixed seed
    randomizer = random.Random(RANDOM_SEED)
    
    # Generate the list of 1,000 events using list comprehension
    events = [
        generate_event(randomizer, index)
        for index in range(1, EVENT_COUNT + 1)
    ]
    
    # Write the formatted JSON array to the output file path
    OUTPUT_PATH.write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(f"Generated {len(events)} events at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()