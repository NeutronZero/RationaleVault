import argparse
from pathlib import Path
import sys

from ...certification import (
    CertificationContext,
    CertificationEngine,
    CertificationConfig,
    plugin_registry
)
from ...certification.stages import (
    DiscoveryStage,
    StaticAnalysisStage,
    CompatibilityStage,
    RuntimeStage,
    ReportingStage
)
from ...certification.renderers import TerminalRenderer, JsonRenderer, MarkdownRenderer
from ...certification.rules.packs import register_core_packs

def register(subparsers):
    parser = subparsers.add_parser("certify", help="Run the Framework Certification Suite on an extension")
    parser.add_argument("path", nargs="?", default=".", help="Path to the extension directory")
    parser.add_argument("--stage", choices=["static", "runtime", "full"], default="full", help="Pipeline stage to run up to")
    parser.add_argument("--output-format", choices=["human", "json", "markdown"], default="human", help="Output format")
    parser.add_argument("--output-file", help="Path to write the report")
    parser.add_argument("--config", default="certification-config.yaml", help="Path to configuration file")
    parser.set_defaults(func=handle_certify)
    return parser

def handle_certify(args: argparse.Namespace):
    # Initialize globals
    register_core_packs()
    plugin_registry.discover_entry_points()
    
    target_path = Path(args.path).resolve()
    config_path = target_path / args.config
    config = CertificationConfig.load(config_path)
    
    context = CertificationContext(
        target_path=target_path,
        config=config
    )
    
    # Build pipeline based on stage
    stages = [DiscoveryStage(), StaticAnalysisStage(), CompatibilityStage()]
    if args.stage in ["runtime", "full"]:
        stages.append(RuntimeStage())
    stages.append(ReportingStage())
    
    engine = CertificationEngine(stages=stages)
    report = engine.run(context)
    
    # Render
    if args.output_format == "json":
        renderer = JsonRenderer()
    elif args.output_format == "markdown":
        renderer = MarkdownRenderer()
    else:
        renderer = TerminalRenderer()
        
    output_str = renderer.render(report)
    
    if args.output_file:
        Path(args.output_file).write_text(output_str, encoding="utf-8")
        print(f"Report written to {args.output_file}")
    else:
        print(output_str)
        
    sys.exit(0 if report.passed else 1)
