import requests
import sys

def query_stella(query: str):
    """Send a query to the Stella API and print the response."""
    try:
        response = requests.post("http://localhost:8001/analyze", json={"query": query, "source": "cli"})
        if response.status_code == 200:
            print("\n" + response.json()["result"] + "\n")
        else:
            print(f"\nError: {response.text}\n")
    except requests.exceptions.RequestException as e:
        print(f"\nError: Failed to connect to the server - {e}\n")

def print_welcome_message():
    """Print a welcome message with example queries for each task type."""
    print("Welcome to Stella!")
    print("Enter a query below or type 'exit' to quit.")
    print("Examples:")
    print("1. Stock Report: '1: Generate a stock report for Tesla'")
    print("2. Company Overview: '2: Give me an overview of Microsoft'")
    print("3. Company News: '3: What is the latest news on Apple'")
    print("4. General News: '4: Latest news on artificial intelligence'")
    print("5. Highlights: '5: Give me todays update on Tesla, Apple, and Microsoft'")
    print("-" * 50)

def main():
    """Run an interactive CLI loop for querying Stella."""
    print_welcome_message()
    while True:
        try:
            query = input("\nEnter your query: ").strip()
            if query.lower() == "exit":
                print("Exiting Stella CLI. Goodbye!")
                break
            if not query:
                print("\nPlease enter a valid query or type 'exit' to quit.\n")
                continue
            query_stella(query)
        except KeyboardInterrupt:
            print("\nExiting Stella CLI. Goodbye!")
            break

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Support single query from command line for backward compatibility
        query = " ".join(sys.argv[1:])
        query_stella(query)
    else:
        # Start interactive mode
        main()