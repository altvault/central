import sys


def confirm(prompt="Do you want to continue?", default=False) -> bool:
    """
    Prompts the user for a yes/no confirmation.

    Args:
        prompt (str): The question presented to the user.
        default (bool): The default action if the user simply presses Enter.
                        Defaults to False ('no').

    Returns:
        bool: True for 'yes', False for 'no'.
    """
    # Format the prompt to indicate the default choice
    if default:
        indicator = "[Y/n]"
    else:
        indicator = "[y/N]"

    full_prompt = f"{prompt} {indicator}: "

    # Define acceptable affirmative and negative responses
    yes_responses = {"y", "yes"}
    no_responses = {"n", "no"}

    while True:
        try:
            choice = input(full_prompt).strip().lower()

            # 1. Determine the result based on input
            if choice == "":
                result = default
            elif choice in yes_responses:
                result = True
            elif choice in no_responses:
                result = False
            else:
                print("Please respond with 'y' or 'n' (or 'yes' or 'no').")
                continue  # Loop back and ask again

            # 2. Show the final interpreted answer
            print(f"-> {'Yes' if result else 'No'}")

            # 3. Return the boolean
            return result

        except KeyboardInterrupt:
            # Handle Ctrl-C gracefully
            print("\nOperation cancelled by user (Ctrl-C).")
            # You can either return False here, or exit the script entirely.
            # Exiting is usually the safest behavior for a script interrupted by Ctrl-C.
            sys.exit(1)
