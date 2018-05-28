Moment = {
        dialog: null,
        dialogShade: null,
        dialogWrapper: null,

        loadScreen: null,
        displayScreen: null,

        request: null,
        currentUrl: null,

        text: {
                processing: "processing (this can take awhile)",
                permalink: "Permalink"
        }
};

Moment.init = function() {
        /* Connect event listeners */
        var mediaLinks = $("a.media-link[target=\"_blank\"]");
        mediaLinks.click(function(e) {
                e.preventDefault();
                Moment.openMedia(this.href);
        });

        /* shade that covers the rest of the page */
        Moment.dialogShade = $("<div>");
        Moment.dialogShade.attr("class", "media-dialog-shade");
        Moment.dialogShade.click(Moment.dismissMedia);
        Moment._hide(Moment.dialogShade);
        $(document.body).append(Moment.dialogShade);

        /* loading container */
        Moment.dialog = $("<div>");
        Moment.dialog.attr("id", "media-dialog");
        Moment.dialog.click(function(event) { event.stopPropagation(); });

        Moment.dialogWrapper = $("<section>");
        Moment.dialogWrapper.attr("class", "media-dialog-wrapper");
        Moment.dialogWrapper.click(Moment.dismissMedia);
        Moment.dialogWrapper.append(Moment.dialog);
        Moment._hide(Moment.dialogWrapper);
        $(document.body).append(Moment.dialogWrapper);

        /* loading screen */
        Moment.loadScreen = $("<div>");
        Moment.loadScreen.attr("class", "media-dialog-load");
        Moment.dialog.append(Moment.loadScreen);

        var loading = $("<span>");
        loading.attr("class", "media-dialog-load-msg");
        loading.text(Moment.text.processing);
        Moment.loadScreen.append(loading);

        /* image display screen */
        Moment.displayScreen = $("<div>");
        Moment.dialog.append(Moment.displayScreen);
};

Moment.openMedia = function(url) {
        Moment._show(Moment.dialogShade);
        Moment._show(Moment.dialogWrapper);
        Moment._show(Moment.loadScreen);
        Moment._hide(Moment.displayScreen);

        Moment.currentUrl = url;

        if (Moment.request !== null)
                Moment.request.abort();

        Moment.request = new XMLHttpRequest();
        Moment.request.open("GET", url, true);
        Moment.request.responseType = "blob";
        Moment.request.onload = function(e) {
                Moment.displayMedia(Moment.request.response);
        };
        Moment.request.send();
};

Moment.displayMedia = function(blob) {
        Moment._show(Moment.dialogShade);
        Moment._show(Moment.dialogWrapper);
        Moment._hide(Moment.loadScreen);
        Moment._show(Moment.displayScreen);

        Moment.displayScreen.empty();
        var image, imageWrap,
            video, videoWrap;
        switch (blob.type) {
        case "image/jpeg":
        case "image/gif":
                image = $("<img>");
                image.attr("src", URL.createObjectURL(blob));

                imageWrap = $("<div>");
                imageWrap.attr("class", "media-dialog-image");
                imageWrap.append(image);
                Moment.displayScreen.append(imageWrap);
                break;
        case "video/webm":
                video = $("<video>");
                video.attr({ src: URL.createObjectURL(blob),
                             controls: true,
                             loop: true });

                videoWrap = $("<div>");
                videoWrap.attr("class", "media-dialog-video");
                videoWrap.append(video);
                Moment.displayScreen.append(videoWrap);
                break;
        default:
                break;
        }

        var permalink = $("<input>");
        permalink.attr({ value: Moment.currentUrl,
                         readonly: true });
        var permalinkWrap = $("<span>");
        permalinkWrap.text(Moment.text.permalink + " ");
        permalinkWrap.append(permalink);
        Moment.displayScreen.append(permalinkWrap);
};

Moment.dismissMedia = function() {
        Moment._hide(Moment.dialogShade);
        Moment._hide(Moment.dialogWrapper);

        if (Moment.request !== null)
                Moment.request.abort();
};

Moment._show = function(element) {
        element.css("display", "block");
};
Moment._hide = function(element) {
        element.css("display", "none");
};

Moment.init();

