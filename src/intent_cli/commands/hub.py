"""Launch the optional local IntHub service."""

from intent_cli.output import error


def cmd_hub_start(args):
    try:
        from apps.inthub_local.launcher import main as launch_main
    except ImportError:
        error("HUB_NOT_CONFIGURED", "IntHub Local is not installed.")
    argv = []
    if getattr(args, "port", None) is not None:
        argv += ["--port", str(args.port)]
    if getattr(args, "no_open", False):
        argv += ["--no-open"]
    launch_main(argv)
