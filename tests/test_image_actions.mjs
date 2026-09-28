import assert from 'node:assert/strict';
import test from 'node:test';
import { Schema } from '../app/web/node_modules/prosemirror-model/dist/index.js';
import { EditorState, NodeSelection, TextSelection } from '../app/web/node_modules/prosemirror-state/dist/index.js';
import { history, undo } from '../app/web/node_modules/prosemirror-history/dist/index.js';
import { selectedImage, removeSelectedImage } from '../app/web/image_actions.mjs';

const schema = new Schema({nodes: {
  doc: {content: 'paragraph+'},
  paragraph: {content: 'inline*', group: 'block'},
  text: {group: 'inline'},
  image: {inline: true, group: 'inline', atom: true, selectable: true,
    attrs: {src: {}, alt: {default: ''}, title: {default: ''}}},
}});

function documentWithImage() {
  return schema.node('doc', null, [schema.node('paragraph', null, [
    schema.text('前文'), schema.node('image', {src: 'images/shot_1.jpg', alt: '示意图'}), schema.text('后文'),
  ])]);
}

test('only an image node selection enables image operations', () => {
  const doc = documentWithImage();
  const state = EditorState.create({schema, doc, selection: NodeSelection.create(doc, 3)});
  assert.equal(selectedImage(state).node.attrs.src, 'images/shot_1.jpg');
  assert.equal(selectedImage(state.apply(state.tr.setSelection(TextSelection.create(doc, 1, 3)))), null);
});

test('image deletion preserves neighboring text and undo restores its attributes', () => {
  const doc = documentWithImage();
  const view = {
    state: EditorState.create({schema, doc, selection: NodeSelection.create(doc, 3), plugins: [history()]}),
    dispatch(transaction) { this.state = this.state.apply(transaction); },
  };
  assert.equal(removeSelectedImage(view), true);
  assert.equal(view.state.doc.textContent, '前文后文');
  assert.equal(view.state.doc.firstChild.childCount, 1);
  assert.equal(undo(view.state, transaction => view.dispatch(transaction)), true);
  assert.equal(view.state.doc.eq(doc), true);
  view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, 1)));
  assert.equal(removeSelectedImage(view), false);
  assert.equal(view.state.doc.eq(doc), true);
});
