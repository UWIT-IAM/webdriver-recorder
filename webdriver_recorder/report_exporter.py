import logging
import os
import shutil
from typing import NoReturn

import jinja2

from webdriver_recorder.models import Outcome, Report

logger = logging.getLogger(__name__)
here = os.path.dirname(os.path.abspath(__file__))


class ReportExporter:
    def __init__(
        self,
        template_dir: str = os.path.join(here, "templates"),
        root_template: str = "report.html",
        static_assets_dir: str = "static",
    ):
        self.template_dir = template_dir
        self.relative_static_dir = static_assets_dir
        self.abs_input_static_dir = os.path.join(self.template_dir, static_assets_dir)
        self.static_assets = []
        if static_assets_dir:
            if os.path.exists(self.abs_input_static_dir):
                self.static_assets = [
                    os.path.join(self.abs_input_static_dir, asset) for asset in os.listdir(self.abs_input_static_dir)
                ]
            else:  # pragma: no cover
                logger.warning(
                    f"Expected {self.abs_input_static_dir} to exist, but it does not. Skipping static asset "
                    f"copying. You can disable this warning by setting `static_assets_dir=None` when creating "
                    f"your ReportExporter instance."
                )

        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        self.template = self.env.get_template(root_template)

    def export_json(
        self, report: Report, dest_directory: str, dest_filename: str = "report.json", exclude_image_data: bool = False
    ) -> str:
        if report.num_failures > 0:
            report.outcome = Outcome.failure

        exclude = None
        if exclude_image_data:
            # This is a complex pydantic filter meaning:
            #   for each result in report,
            #   for each png in result,
            #   ignore the 'base64' field.
            logger.info("Stripping base64 image data from report.json")
            exclude = {"results": {"__all__": {"pngs": {"__all__": {"base64"}}}}}
        filename = os.path.join(dest_directory, dest_filename)
        with open(filename, "w") as f:
            f.write(report.json(indent=4, exclude=exclude))
        logger.info(f"Report JSON saved to {filename}")
        return filename

    def export_static(self, dest_directory: str):
        abs_dest_static_dir = os.path.join(dest_directory, self.relative_static_dir)
        for asset in self.static_assets:
            destination = os.path.abspath(os.path.join(abs_dest_static_dir, os.path.basename(asset)))
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copyfile(asset, destination)
            logger.info(f"Copied static asset {asset} to {destination}")

    def export_all(self, report: Report, dest_directory: str):
        # If we write images to disk, don't include base64 of the
        # images in the exported json.
        # This will still preserve image metadata, including its filename.
        self.export_json(report, dest_directory=dest_directory, exclude_image_data=True)
        self.export_images(report, dest_directory=dest_directory)
        self.export_static(dest_directory=dest_directory)
        self.export_html(report, dest_directory=dest_directory)

    def export_html(self, report: Report, dest_directory: str, dest_filename: str = "index.html"):
        dest_filename = os.path.join(dest_directory, dest_filename)
        stream = self.template.stream(report=report)
        stream.dump(dest_filename)
        logger.info(f"Exported report HTML to {dest_filename}")

    @classmethod
    def export_images(cls, report: Report, dest_directory: str) -> NoReturn:
        for test in report.results:
            for image in filter(lambda i: i.base64, test.pngs):
                image.save(dest_directory)
                logger.info(f"Saved image {image.url}")
