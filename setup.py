"""
Setup file for the ecommerce-hyperpay Open edX ecommerce payment processor backend plugin.
"""

from pathlib import Path

from setuptools import setup

README = open(Path(__file__).parent / 'README.rst').read()
CHANGELOG = open(Path(__file__).parent / 'CHANGELOG.rst').read()


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
        'Django~=2.2',
    ],
    packages=[
        'hyperpay',
    ],
    entry_points={
        'ecommerce': [
            'hyperpay = hyperpay.apps:HyperPayConfig',
        ],
    },
)
