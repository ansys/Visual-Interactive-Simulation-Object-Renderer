# AWC Fonts & Icon Library Generator Readme

## Overview

In order to make use of AWC fonts and icons without installing the entire AWC React npm package, we need to import the static assets that the AWC React npm package uses. These assets include the following:

- The default AWC UI font (Source Sans 3) and its corresponding CSS font-family stack
- AWC icon SVGs

Lastly, due to the large number of AWC icon SVG files, there was a need for automating the creation of a JavaScript AWC icon library based on a given list of icon names. This automation resulted in the `awc-icon-generator.html` file found in the VISOR repository.

The following sections elaborate on obtaining the AWC font and its font stack, as well as the design behind the `awc-icon-generator.html` file found in the VISOR repository.

## Default AWC UI Font

As of 2025-04-17, the font stack for AWC UI text is the following:

```css
.awc-text {
    font-family: "Source Sans 3",
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Roboto,
    "Noto Sans",
    Ubuntu,
    Cantarell,
    "Helvetica Neue",
    sans-serif,
    "Apple Color Emoji",
    "Segoe UI Emoji",
    "Segoe UI Symbol",
    "Noto Color Emoji";
}
```

As you can see, the primary font is Source Sans 3. This font stack can be found in the following CSS file (after installing the AWC React npm package):

**@ansys\awc-react\styles\themes\css\default.css**

Alternatively, the easiest way to get this font stack is to visit https://prerelease.awc.ansys.com/#/d/icons, open your browser's F12 developer tools, and inspect an element that uses the font using the "DOM and Style Inspector" to see the element's font-family.

Acquiring the "Source Sans 3" font is straightforward. Source Sans 3 can be downloaded from Google Fonts at https://fonts.google.com/specimen/Source+Sans+3.

## AWC Icon SVGs

The actual SVG markup that each AWC icon uses is not included in the AWC npm package. When using the AWC npm package in your application, your frontend will actually make a request to an `amazonaws` url (as of 2025-04-17) to download each icon on an as-needed basis.

The list of icons available at that url (minus the .svg extension) can be found in the following TypeScript file after installing the AWC package:

**@ansys\awc-react\core\types\icon.enum.d.ts**

Note that the list of icons found in the file above does not include each icon's url, rather only its name (minus the .svg extension). In order to get the full url for each icon, we must know the AWC icon base url. The AWC icon base url can be found in the following JavaScript file:

**@ansys\awc-react\types\awc.js**

In that file, base url string is set to a variable that looks like this:

```javascript
AWC.BASE_ICON_ROUTE = 'https://ansys-web-components.s3.eu-west-2.amazonaws.com/os-icons/v3/';
```

**So, if you wanted to download the SVG for the "add-circle" icon, the url would be the following:**

`https://ansys-web-components.s3.eu-west-2.amazonaws.com/os-icons/v3/add-circle.svg`

The easiest way to get this icon list is to just
visit https://prerelease.awc.ansys.com/#/d/icons, open your browser's F12 developer tools,
go to the network tab, and see where all the icon SVGs on the page are being
downloaded from. This method saves you from having to install the entire AWC npm package
just to get the base url.

## AWC Icon Generator (awc-icon-generator.html)

Traditionally, when websites used icon packs, the website would deploy a single .woff font that included each icon as a glyph. In AWC however, each icon is an SVG element. This allows for more flexibility with each icon, such as being able to give different parts of the same icon different colors. This was not possible with the traditional icon font packs. However, the tradeoff with SVGs is that there is a little more setup required to deploy them than there is with a font pack. The way AWC typically renders icons on the frontend is by making a request for each icon's SVG from an `amazonaws` URL.

Since we wanted to use these AWC icons without installing the AWC package, we needed to download all the SVGs and serve them locally. This way, if the icon URLs became obsolete, it would not affect our application.

VISOR inserts AWC icons into React components (or anywhere in JavaScript for that matter) by making use of a dynamically-created `AwcIcons.js` file. This JavaScript library is created by the `awc-icon-generator.html` page, which can actually be run independent of VISOR.

The `awc-icon-generator.html` page generates JavaScript inside a &lt;textarea&gt; input, that can be copy-pasted into the `AwcIcons.js` file any time AWC updates its icon collection.