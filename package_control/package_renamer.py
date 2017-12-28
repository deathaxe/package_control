import os
import time

import sublime

from .console_write import console_write
from .settings import load_list_setting
from .settings import pc_settings_filename
from .settings import save_list_setting


class PackageRenamer(object):

    """
    Class to handle renaming packages via the renamed_packages setting
    gathered from channels and repositories.
    """

    def __init__(self):
        """
        Initiate new PackageRenamer object
        """

        self.original_installed_packages = None

    def load_settings(self):
        """
        Loads the list of installed packages
        """

        settings = sublime.load_settings(pc_settings_filename())
        self.original_installed_packages = load_list_setting(settings, 'installed_packages')

    def rename_packages(self, installer):
        """
        Renames any installed packages that the user has installed.

        :param installer:
            An instance of :class:`PackageInstaller`
        """

        # Fetch the packages since that will pull in the renamed packages list
        installer.manager.list_available_packages()
        renamed_packages = installer.manager.settings.get('renamed_packages', {})

        if not renamed_packages:
            renamed_packages = {}

        # These are packages that have been tracked as installed
        installed_packages = list(self.original_installed_packages)
        # There are the packages actually present on the filesystem
        present_packages = installer.manager.list_packages()

        case_insensitive_fs = sublime.platform() in ['windows', 'osx']

        # Rename directories for packages that have changed names
        for package_name, new_package_name in renamed_packages.items():
            changing_case = package_name.lower() == new_package_name.lower()

            # Since Windows and OSX use case-insensitive filesystems, we have to
            # scan through the list of installed packages if the rename of the
            # package is just changing the case of it. If we don't find the old
            # name for it, we continue the loop since os.path.exists() will return
            # true due to the case-insensitive nature of the filesystems.
            if case_insensitive_fs and changing_case and package_name not in present_packages:
                continue

            # For handling .sublime-package files
            package_file = os.path.join(sublime.installed_packages_path(), package_name + '.sublime-package')
            # For handling unpacked packages
            package_dir = os.path.join(sublime.packages_path(), package_name)

            if os.path.exists(package_file):
                new_package_path = os.path.join(
                    sublime.installed_packages_path(),
                    new_package_name + '.sublime-package'
                )
                package_path = package_file
            elif os.path.exists(os.path.join(package_dir, 'package-metadata.json')):
                new_package_path = os.path.join(sublime.packages_path(), new_package_name)
                package_path = package_dir
            else:
                continue

            installer.disable_packages(package_name, 'remove')

            remove_result = True
            if not os.path.exists(new_package_path) or (case_insensitive_fs and changing_case):
                installer.disable_packages(new_package_name, 'install')
                time.sleep(0.7)

                # Windows will not allow you to rename to the same name with
                # a different case, so we work around that with a temporary name
                if os.name == 'nt' and changing_case:
                    temp_package_name = '__' + new_package_name
                    temp_package_path = os.path.join(
                        os.path.dirname(sublime.packages_path()), temp_package_name
                    )
                    os.rename(package_path, temp_package_path)
                    package_path = temp_package_path

                os.rename(package_path, new_package_path)
                installed_packages.append(new_package_name)

                console_write(
                    '''
                    Renamed %s to %s
                    ''',
                    (package_name, new_package_name)
                )
                installer.reenable_package(new_package_name, 'install')

            else:
                time.sleep(0.7)
                remove_result = installer.manager.remove_package(package_name)

                console_write(
                    '''
                    Removed %s since package with new name (%s) already exists
                    ''',
                    (package_name, new_package_name)
                )

            # Do not reenable if removal has been delayed until next restart
            if remove_result is not None:
                installer.reenable_package(package_name, 'remove')

            try:
                installed_packages.remove(package_name)
            except (ValueError):
                pass

        self.save_packages(installed_packages)

    def save_packages(self, installed_packages):
        """
        Saves the list of installed packages (after having been appropriately
        renamed)

        :param installed_packages:
            The new list of installed packages
        """

        filename = pc_settings_filename()
        settings = sublime.load_settings(filename)
        save_list_setting(
            settings,
            filename,
            'installed_packages',
            installed_packages,
            self.original_installed_packages
        )
