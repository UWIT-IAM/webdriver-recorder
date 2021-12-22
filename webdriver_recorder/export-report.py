import argparse
import logging
import os

from webdriver_recorder.models import Report
from webdriver_recorder.report_exporter import ReportExporter

here = os.path.dirname(os.path.abspath(__file__))


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        "Regenerates a report from an existing report.json using a custom or default template. "
        "This makes it easier to tweak the template without having to run a full test suite each time, "
        "as long as the report.json appears correct."
    )
    parser.add_argument("--input-json", "-i", required=True, help="The path to the report.json you want to load.")
    parser.add_argument(
        "--output-dir",
        "-o",
        required=False,
        default=None,
        help="The directory you want the report output to go. If not provided, it will overwrite "
        "the input report artifacts.",
    )
    parser.add_argument(
        "--template-filename",
        "-t",
        required=False,
        default=os.path.join(here, "templates", "report.html"),
        help="The name of a template to use when generating the report.",
    )
    return parser


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    args = get_parser().parse_args()
    output_dir = args.output_dir or os.path.dirname(args.input_json)
    exporter = ReportExporter(
        template_dir=os.path.dirname(args.template_filename), root_template=os.path.basename(args.template_filename)
    )
    report = Report.parse_file(args.input_json)
    exporter.export_all(report, output_dir)
    print(f"Exported artifacts to {output_dir}")
