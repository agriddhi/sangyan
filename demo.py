"""Run real examples through the rule engine and print what it found.

Usage (from the sangyan folder):  python demo.py
"""

from app.engine.rules import ROUTE_INFO, choose_route, evaluate

EXAMPLES = [
    (
        "Forwarded 'investment' message",
        "Guaranteed 3% monthly returns. Send your PAN, Aadhaar and cancelled "
        "cheque on WhatsApp to activate your account.",
    ),
    (
        "Hindi pressure message",
        "आपका खाता बंद हो जाएगा। अपना ओटीपी और पिन भेजें।",
    ),
    (
        "Normal bank message",
        "Hi, your SIP of Rs 5,000 for October has been processed. "
        "You can see the details in the official app.",
    ),
]


def show(title: str, text: str) -> None:
    print("=" * 72)
    print(title)
    print("-" * 72)
    print(f"INPUT: {text}")
    print()

    signals = evaluate(text)
    if not signals:
        print("No signals found in this message.")
    for signal in signals:
        print(f"[{signal.severity.upper():8}] {signal.rule_id}")
        print(f"           {signal.title}")
        print(f"           quote: {signal.source_quote}")
    print()

    decision = choose_route(text, signals)
    info = ROUTE_INFO[decision.route_id]
    print(f"ROUTE: {decision.route_id} ({info['name']})")
    print(f"WHY:   {decision.reason}")
    print()


if __name__ == "__main__":
    for example_title, example_text in EXAMPLES:
        show(example_title, example_text)
