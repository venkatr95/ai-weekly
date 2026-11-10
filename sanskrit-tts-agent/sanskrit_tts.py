"""Write sanskrit_output.mp3 for the Ganesha sloka."""

from sanskrit_tts_core import GANESHA_SLOKA, generate_sanskrit_audio


def main() -> None:
    generate_sanskrit_audio(GANESHA_SLOKA, "sanskrit_output.mp3")


if __name__ == "__main__":
    main()
