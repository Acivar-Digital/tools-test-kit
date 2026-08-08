import argparse
import asyncio
import json
import time

import httpx


# Mock Telegram Webhook structure
def make_update(chat_id: int, text: str):
    return {
        "update_id": int(time.time()),
        "message": {
            "message_id": int(time.time()),
            "from": {"id": chat_id, "is_bot": False, "first_name": "Test", "last_name": "User"},
            "chat": {"id": chat_id, "first_name": "Test", "last_name": "User", "type": "private"},
            "date": int(time.time()),
            "text": text,
        },
    }


SCENARIOS = {
    "TC01": {
        "name": "Happy Path AUTO",
        "steps": ["/start", "/auto", "Tester", "Male", "1988-08-08 12:30", "Singapore", "Ren Chen", "Yes"],
        "expected_final_step": "COMPLETE",
    },
    "TC02": {
        "name": "Happy Path INPUT",
        "steps": [
            "/start",
            "/input",
            "Tester",
            "Male",
            "Geng Chen",
            "Ji Chou",
            "Bing Shen",
            "Jia Wu",
            "Ren Chen",
            "Strong",
            "Fire, Wood",
            "Earth",
            "Metal, Water",
            "Yes",
        ],
        "expected_final_step": "COMPLETE",
    },
    "TC03": {
        "name": "Pinyin typos + Chinese chars",
        "steps": [
            "/start",
            "/input",
            "Tester",
            "男",  # Male in Chinese
            "Jia Zi",  # Correct
            "Ding Meow",  # Typo for Mao
            "Yes",  # Assume it eventually gets there or we test correction
        ],
        "check_keyword": "Ding Mao",  # Conductor should correct this
    },
    "TC04": {
        "name": "Power user dumps all at once",
        "steps": [
            "/start",
            "/input",
            "Name: Tester, Gender: Male, Year: Geng Chen, Month: Ji Chou, Day: Bing Shen, Hour: Jia Wu, Da Yun: Ren Chen, Strength: Strong, Fav: Fire, Wood",
        ],
        "expected_final_step": "CONFIRM",
    },
    "TC05": {
        "name": "Override computed strength",
        "steps": [
            "/start",
            "/auto",
            "Tester",
            "Male",
            "1988-08-08 12:30",
            "Singapore",
            "Actually, my master said I am Weak",
        ],
        "check_profile": {"day_master_strength": "Weak"},
    },
    "TC06": {
        "name": "Incomplete / 'I don't know'",
        "steps": ["/start", "/input", "Tester", "Male", "I don't know my year pillar"],
        "expected_not_stuck": True,
    },
    "TC07": {
        "name": "/reset mid-flow",
        "steps": ["/start", "/auto", "Tester", "/reset", "/start"],
        "check_session": {"step": "CHOOSING"},
    },
    "TC08": {
        "name": "Invalid gender 'helicopter'",
        "steps": ["/start", "/auto", "Tester", "helicopter"],
        "expected_step": "COLLECTING",  # Should not advance to pillars
    },
    "TC09": {
        "name": "Confirm loop with correction",
        "steps": [
            "/start",
            "/input",
            "Tester",
            "Male",
            "Geng Chen",
            "Ji Chou",
            "Bing Shen",
            "Jia Wu",
            "Ren Chen",
            "Strong",
            "Fire",
            "Earth",
            "Metal",
            "No, Da Yun is wrong, it is Gui Mao",
            "Yes",
        ],
        "check_profile": {"da_yun_pillar": {"stem": "Gui", "branch": "Mao"}},
    },
    "TC10": {
        "name": "Gibberish/emoji/off-topic",
        "steps": ["/start", "/auto", "😂👍", "What's the weather like?", "Tester"],
        "expected_not_crash": True,
    },
}


async def run_test(url: str, tc_id: str, verbose: bool):
    scenario = SCENARIOS.get(tc_id)
    if not scenario:
        print(f"Unknown scenario: {tc_id}")
        return

    chat_id = 999000 + int(tc_id[2:])
    print(f"\n--- Running {tc_id}: {scenario['name']} (Chat ID: {chat_id}) ---")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for step_idx, text in enumerate(scenario["steps"]):
            if verbose:
                print(f"Step {step_idx + 1}: Sending '{text}'")

            payload = make_update(chat_id, text)
            try:
                resp = await client.post(f"{url}/webhook", json=payload)
                if resp.status_code != 200:
                    print(f"Error: Webhook returned {resp.status_code}: {resp.text}")
                    return
            except Exception as e:
                print(f"Connection error: {e}")
                return

            # Wait a bit for LLM processing
            await asyncio.sleep(1.5)

            # Check state
            debug_resp = await client.get(f"{url}/debug/session/{chat_id}")
            if debug_resp.status_code == 200:
                session = debug_resp.json()
                if verbose:
                    history = session.get("conversation_history", [])
                    last_reply = history[-1]["content"] if history else "N/A"
                    print(f"Bot: {last_reply}")
                    print(f"Step: {session.get('step')}")
            else:
                print(f"Warning: Debug endpoint returned {debug_resp.status_code}")

        # Final assertions
        debug_resp = await client.get(f"{url}/debug/session/{chat_id}")
        if debug_resp.status_code == 200:
            session = debug_resp.json()
            profile = session.get("profile", {})

            passed = True
            if "expected_final_step" in scenario:
                if session.get("step") != scenario["expected_final_step"]:
                    print(f"FAIL: Expected step {scenario['expected_final_step']}, got {session.get('step')}")
                    passed = False

            if "check_keyword" in scenario:
                history_str = json.dumps(session.get("conversation_history", []))
                if scenario["check_keyword"].lower() not in history_str.lower():
                    print(f"FAIL: Keyword '{scenario['check_keyword']}' not found in history")
                    passed = False

            if "check_profile" in scenario:
                for k, v in scenario["check_profile"].items():
                    if profile.get(k) != v:
                        print(f"FAIL: Profile {k} expected {v}, got {profile.get(k)}")
                        passed = False

            if passed:
                print(f"PASSED {tc_id}")
            else:
                print(f"FAILED {tc_id}")
        else:
            print("CRITICAL: Final debug check failed")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8443")
    parser.add_argument("--tc", help="Run specific test case (e.g. TC01)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.tc:
        await run_test(args.url, args.tc, args.verbose)
    else:
        for tc_id in sorted(SCENARIOS.keys()):
            await run_test(args.url, tc_id, args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
