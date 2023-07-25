"""
Setup file for the ecommerce-hyperpay Open edX ecommerce payment processor backend plugin.
"""
import os

from pathlib import Path

from setuptools import setup

README = open(Path(__file__).parent / 'README.rst').read()
CHANGELOG = open(Path(__file__).parent / 'CHANGELOG.rst').read()

def package_data(pkg, roots):
    """Generic function to find package_data.

    All of the files under each of the `roots` will be declared as package
    data for package `pkg`.

    """
    data = []
    for root in roots:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}


setup(
    name='hyperpay-ecommerce',
    description='HyperPay ecommerce payment processor backend plugin',
    version='0.1.0',
    author='OpenCraft',
    author_email='contact@opencraft.com',
    long_description=f'{README}\n\n{CHANGELOG}',
    long_description_content_type='text/x-rst',
    url='https://github.com/open-craft/ecommerce-hyperpay',
    include_package_data=True,
    zip_safe=False,
    keywords='Django openedx openedx-plugin ecommerce hyperpay',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Django',
        'Framework :: Django :: 2.2',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
    ],
    install_requires=[
        'Django~=3.2',
    ],
    package_data=package_data('hyperpay', ['locale']),
    packages=[
        'hyperpay',
    ],
    entry_points={
        'ecommerce': [
            'hyperpay = hyperpay.apps:HyperPayConfig',
        ],
    },
)
