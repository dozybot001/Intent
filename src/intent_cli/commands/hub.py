"""Launch the optional local IntHub service."""

from intent_cli.output import error


def cmd_hub_start(args):
    try:
        from apps.inthub_local.launcher import main as launch_main
    except ImportError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        error(
            "HUB_NOT_CONFIGURED",
            f"IntHub Local could not start: Python module {missing!r} is unavailable.",
            suggested_fix="Reinstall Intent with its bundled IntHub Local files, then retry `itt hub start`.",
        )
    argv = []
    if getattr(args, "port", None) is not None:
        argv += ["--port", str(args.port)]
    if getattr(args, "no_open", False):
        argv += ["--no-open"]
    launch_main(argv)
